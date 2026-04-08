"""draw.io XML generator — Phase B core.

Converts topology Pydantic models (cna.core.topology_schema) into
draw.io-compatible XML strings. Handles XML-unsafe characters, empty
resource sets, and oversized topologies gracefully.

Supported diagram types:
  - vpc_topology       : VPC + subnets + IGW + NAT + route table summary
  - vnet_topology      : VNet + subnets + peerings + route tables
  - tgw_topology       : Transit Gateway hub-and-spoke
  - vwan_topology      : Azure Virtual WAN hub-and-spoke
  - account_hierarchy  : AWS org tree (Mermaid, see mermaid_generator.py)
  - mg_hierarchy       : Azure management group tree (Mermaid)

Export pipeline:
  XML string -> .drawio file -> export_pipeline.py -> .svg -> .png -> .pdf
"""

from __future__ import annotations

import html
import textwrap
import uuid

from cna.core.topology_schema import (
    AWSRegionTopology,
    AzureSubscriptionTopology,
    AzureVWan,
    SubnetType,
    TransitGateway,
)

# ── Draw.io style constants ─────────────────────────────────────────────────

STYLE_VPC = (
    "rounded=1;whiteSpace=wrap;html=1;"
    "fillColor=#dae8fc;strokeColor=#6c8ebf;fontSize=11;fontStyle=1;"
    "verticalAlign=top;"
)
STYLE_VNET = (
    "rounded=1;whiteSpace=wrap;html=1;"
    "fillColor=#d5e8d4;strokeColor=#82b366;fontSize=11;fontStyle=1;"
    "verticalAlign=top;"
)
STYLE_SUBNET_PUBLIC = (
    "rounded=0;whiteSpace=wrap;html=1;fillColor=#fff2cc;strokeColor=#d6b656;fontSize=10;"
)
STYLE_SUBNET_PRIVATE = (
    "rounded=0;whiteSpace=wrap;html=1;fillColor=#f8cecc;strokeColor=#b85450;fontSize=10;"
)
STYLE_SUBNET_ISOLATED = (
    "rounded=0;whiteSpace=wrap;html=1;fillColor=#e1d5e7;strokeColor=#9673a6;fontSize=10;"
)
STYLE_SUBNET_UNKNOWN = (
    "rounded=0;whiteSpace=wrap;html=1;fillColor=#f5f5f5;strokeColor=#666666;fontSize=10;"
)
STYLE_IGW = (
    "shape=mxgraph.aws4.resourceIcon;resIcon=mxgraph.aws4.internet_gateway;"
    "fillColor=#FF8000;strokeColor=#ffffff;fontStyle=1;fontSize=10;"
)
STYLE_NAT = (
    "shape=mxgraph.aws4.resourceIcon;resIcon=mxgraph.aws4.nat_gateway;"
    "fillColor=#8C4FFF;strokeColor=#ffffff;fontStyle=1;fontSize=10;"
)
STYLE_TGW = (
    "shape=mxgraph.aws4.resourceIcon;resIcon=mxgraph.aws4.transit_gateway;"
    "fillColor=#8C4FFF;strokeColor=#ffffff;fontStyle=1;fontSize=10;"
)
STYLE_VWAN_HUB = (
    "shape=mxgraph.azure2.virtual_hub;"
    "fillColor=#0078D4;strokeColor=#ffffff;fontStyle=1;fontSize=10;"
)
STYLE_EDGE = "edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;exitX=0.5;"

SUBNET_STYLES: dict[SubnetType, str] = {
    SubnetType.PUBLIC: STYLE_SUBNET_PUBLIC,
    SubnetType.PRIVATE: STYLE_SUBNET_PRIVATE,
    SubnetType.ISOLATED: STYLE_SUBNET_ISOLATED,
    SubnetType.UNKNOWN: STYLE_SUBNET_UNKNOWN,
}

# ── Layout constants ─────────────────────────────────────────────────────

VPC_X_GAP = 60  # horizontal gap between VPCs
VPC_Y_START = 80
SUBNET_W = 180
SUBNET_H = 60
SUBNET_COL_GAP = 20
SUBNET_ROW_GAP = 20
SUBNET_PADDING = 20  # padding inside VPC container
ICON_W = 48
ICON_H = 48
SUBNETS_PER_ROW = 4
VPC_HEADER_H = 36
NAT_X_GAP = 60  # FIX P2: horizontal gap between NAT gateway icons


def _safe(text: str | None) -> str:
    """Escape XML-unsafe characters. Handles None gracefully."""
    if not text:
        return ""
    return html.escape(str(text), quote=True)


def _cell_id() -> str:
    return str(uuid.uuid4()).replace("-", "")[:16]


def _vpc_dims(subnet_count: int) -> tuple[int, int]:
    """Calculate VPC container width/height from subnet count."""
    cols = min(subnet_count, SUBNETS_PER_ROW) if subnet_count > 0 else 1
    rows = max(1, -(-subnet_count // SUBNETS_PER_ROW))  # ceiling div
    w = SUBNET_PADDING * 2 + cols * SUBNET_W + (cols - 1) * SUBNET_COL_GAP
    h = (
        VPC_HEADER_H
        + SUBNET_PADDING
        + rows * SUBNET_H
        + (rows - 1) * SUBNET_ROW_GAP
        + SUBNET_PADDING
    )
    return w, h


# ── XML helpers ───────────────────────────────────────────────────────────


def _container_cell(cell_id: str, label: str, x: int, y: int, w: int, h: int, style: str) -> str:
    return (
        f'<mxCell id="{cell_id}" value="{_safe(label)}" style="{style}" '
        f'vertex="1" parent="1">'
        f'<mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" as="geometry"/>'
        f"</mxCell>\n"
    )


def _child_cell(
    cell_id: str, label: str, x: int, y: int, w: int, h: int, style: str, parent_id: str
) -> str:
    return (
        f'<mxCell id="{cell_id}" value="{_safe(label)}" style="{style}" '
        f'vertex="1" parent="{parent_id}">'
        f'<mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" as="geometry"/>'
        f"</mxCell>\n"
    )


def _edge_cell(src: str, tgt: str, label: str = "") -> str:
    eid = _cell_id()
    return (
        f'<mxCell id="{eid}" value="{_safe(label)}" style="{STYLE_EDGE}" '
        f'edge="1" source="{src}" target="{tgt}" parent="1">'
        f'<mxGeometry relative="1" as="geometry"/>'
        f"</mxCell>\n"
    )


def _wrap_diagram(cells: str, label: str) -> str:
    return textwrap.dedent(f"""\
        <mxfile host="CNA" version="21.0.0">
          <diagram name="{_safe(label)}">
            <mxGraphModel dx="1422" dy="762" grid="1" gridSize="10"
              connect="1" arrows="1" fold="1" page="0"
              pageScale="1" pageWidth="1169" pageHeight="827"
              math="0" shadow="0">
              <root>
                <mxCell id="0"/>
                <mxCell id="1" parent="0"/>
                {cells}
              </root>
            </mxGraphModel>
          </diagram>
        </mxfile>
    """)


# ── VPC Topology ───────────────────────────────────────────────────────────


def generate_vpc_topology(region_topology: AWSRegionTopology) -> str:
    """Generate draw.io XML for all VPCs in a single AWS region.

    Args:
        region_topology: Discovered AWSRegionTopology for one account+region.

    Returns:
        draw.io XML string. Empty diagram with a note if no VPCs discovered.

    Raises:
        ValueError: If region_topology.discovery_blocked is True
          (caller should check before invoking).
    """
    if region_topology.discovery_blocked:
        raise ValueError(
            f"Discovery was blocked for "
            f"{region_topology.account_id}/{region_topology.region}: "
            f"{region_topology.block_reason}. "
            "Cannot generate diagram from incomplete data."
        )

    cells = ""
    cursor_x = 40

    if not region_topology.vpcs:
        note_id = _cell_id()
        cells += _container_cell(
            note_id,
            f"No VPCs found in {region_topology.account_id} / {region_topology.region}",
            40,
            80,
            400,
            60,
            "text;html=1;strokeColor=none;fillColor=#ffe6cc;align=center;",
        )
        label = f"VPC Topology — {region_topology.account_id} / {region_topology.region} (empty)"
        return _wrap_diagram(cells, label)

    for vpc in region_topology.vpcs:
        subnet_count = len(vpc.subnets)
        vpc_w, vpc_h = _vpc_dims(subnet_count)
        vpc_id = _cell_id()
        vpc_label = f"{vpc.name or vpc.id}\n{vpc.cidr}" + (" [default]" if vpc.is_default else "")
        cells += _container_cell(vpc_id, vpc_label, cursor_x, VPC_Y_START, vpc_w, vpc_h, STYLE_VPC)

        # Subnets inside VPC container
        for idx, subnet in enumerate(vpc.subnets):
            col = idx % SUBNETS_PER_ROW
            row = idx // SUBNETS_PER_ROW
            sx = SUBNET_PADDING + col * (SUBNET_W + SUBNET_COL_GAP)
            sy = VPC_HEADER_H + SUBNET_PADDING + row * (SUBNET_H + SUBNET_ROW_GAP)
            sn_id = _cell_id()
            sn_label = (
                f"{subnet.name or subnet.id}\n"
                f"{subnet.cidr} | {subnet.az}\n"
                f"[{subnet.subnet_type.value}]"
                + (" \U0001f512" if not subnet.auto_assign_public_ip else " \U0001f310")
            )
            style = SUBNET_STYLES.get(subnet.subnet_type, STYLE_SUBNET_UNKNOWN)
            cells += _child_cell(sn_id, sn_label, sx, sy, SUBNET_W, SUBNET_H, style, vpc_id)

        # IGW icon centered above VPC
        igw_ids = []
        for igw in vpc.internet_gateways:
            igw_id = _cell_id()
            igw_x = cursor_x + vpc_w // 2 - ICON_W // 2
            igw_y = VPC_Y_START - ICON_H - 20
            igw_label = igw.name or igw.id
            cells += _container_cell(igw_id, igw_label, igw_x, igw_y, ICON_W, ICON_H, STYLE_IGW)
            cells += _edge_cell(igw_id, vpc_id)
            igw_ids.append(igw_id)

        # FIX P2: NAT gateway icons laid out horizontally below the VPC.
        # nat_x advances by NAT_X_GAP per gateway so multi-AZ NATs
        # (a common prod pattern) are distinct nodes, not stacked on top of each other.
        nat_base_x = cursor_x + SUBNET_PADDING
        nat_y = VPC_Y_START + vpc_h + 10
        for nat_idx, nat in enumerate(vpc.nat_gateways):
            nat_id = _cell_id()
            nat_x = nat_base_x + nat_idx * (ICON_W + NAT_X_GAP)
            nat_label = f"{nat.name or nat.id}\n{nat.public_ip or ''}"
            cells += _container_cell(nat_id, nat_label, nat_x, nat_y, ICON_W, ICON_H, STYLE_NAT)
            cells += _edge_cell(vpc_id, nat_id)

        cursor_x += vpc_w + VPC_X_GAP

    # TGW layer below all VPCs
    tgw_y = VPC_Y_START + 500
    tgw_x_start = 40
    for tgw in region_topology.transit_gateways:
        tgw_id = _cell_id()
        tgw_label = f"{tgw.name or tgw.id}\nASN:{tgw.amazon_side_asn or 'N/A'}"
        cells += _container_cell(
            tgw_id, tgw_label, tgw_x_start, tgw_y, ICON_W * 2, ICON_H * 2, STYLE_TGW
        )
        tgw_x_start += ICON_W * 2 + 60

    label = f"VPC Topology — {region_topology.account_id} / {region_topology.region}"
    return _wrap_diagram(cells, label)


# ── VNet Topology ──────────────────────────────────────────────────────────


def generate_vnet_topology(sub_topology: AzureSubscriptionTopology) -> str:
    """Generate draw.io XML for all VNets in an Azure subscription."""
    if sub_topology.discovery_blocked:
        raise ValueError(
            f"Discovery was blocked for subscription "
            f"{sub_topology.subscription_id}: {sub_topology.block_reason}. "
            "Cannot generate diagram from incomplete data."
        )

    cells = ""
    cursor_x = 40

    if not sub_topology.vnets:
        note_id = _cell_id()
        cells += _container_cell(
            note_id,
            f"No VNets found in subscription {sub_topology.subscription_id}",
            40,
            80,
            420,
            60,
            "text;html=1;strokeColor=none;fillColor=#ffe6cc;align=center;",
        )
        label = f"VNet Topology — {sub_topology.subscription_id} (empty)"
        return _wrap_diagram(cells, label)

    for vnet in sub_topology.vnets:
        subnet_count = len(vnet.subnets)
        vnet_w, vnet_h = _vpc_dims(subnet_count)
        vnet_id = _cell_id()
        vnet_label = (
            f"{vnet.name}\n{', '.join(vnet.address_space)}\n{vnet.location} | {vnet.resource_group}"
        )
        cells += _container_cell(
            vnet_id, vnet_label, cursor_x, VPC_Y_START, vnet_w, vnet_h, STYLE_VNET
        )

        for idx, subnet in enumerate(vnet.subnets):
            col = idx % SUBNETS_PER_ROW
            row = idx // SUBNETS_PER_ROW
            sx = SUBNET_PADDING + col * (SUBNET_W + SUBNET_COL_GAP)
            sy = VPC_HEADER_H + SUBNET_PADDING + row * (SUBNET_H + SUBNET_ROW_GAP)
            sn_id = _cell_id()
            nsg_indicator = " \U0001f512" if subnet.nsg_id else " \u26a0\ufe0f"
            sn_label = (
                f"{subnet.name}\n"
                f"{subnet.address_prefix}"
                + (f"\n{subnet.delegation}" if subnet.delegation else "")
                + nsg_indicator
            )
            cells += _child_cell(
                sn_id, sn_label, sx, sy, SUBNET_W, SUBNET_H, STYLE_SUBNET_PRIVATE, vnet_id
            )

        for peering in vnet.peerings:
            peer_note_id = _cell_id()
            peer_x = cursor_x + vnet_w + 40
            peer_y = VPC_Y_START + 20
            remote_name = peering.remote_vnet_name or peering.remote_vnet_id.split("/")[-1]
            cells += _container_cell(
                peer_note_id,
                f"\u21c4 {remote_name}\n[{peering.peering_state}]",
                peer_x,
                peer_y,
                160,
                50,
                "rounded=1;fillColor=#fff2cc;strokeColor=#d6b656;fontSize=9;",
            )
            cells += _edge_cell(vnet_id, peer_note_id, peering.name)

        cursor_x += vnet_w + VPC_X_GAP

    label = f"VNet Topology — {sub_topology.subscription_id}"
    return _wrap_diagram(cells, label)


# ── TGW Hub-and-Spoke ──────────────────────────────────────────────────────


def generate_tgw_topology(tgw: TransitGateway, region_topology: AWSRegionTopology) -> str:
    """Generate draw.io XML for a single Transit Gateway and all its attachments."""
    import math

    cells = ""
    center_x, center_y = 500, 400
    tgw_id = _cell_id()
    tgw_label = f"{tgw.name or tgw.id}\n{tgw.owner_account_id}\nASN:{tgw.amazon_side_asn or 'N/A'}"
    cells += _container_cell(
        tgw_id, tgw_label, center_x, center_y, ICON_W * 2, ICON_H * 2, STYLE_TGW
    )

    count = len(tgw.attachments)
    radius = max(250, count * 40)
    for i, attachment in enumerate(tgw.attachments):
        angle = (2 * math.pi * i) / max(count, 1)
        ax = int(center_x + radius * math.cos(angle) - SUBNET_W // 2)
        ay = int(center_y + radius * math.sin(angle) - SUBNET_H // 2)
        att_id = _cell_id()
        display_name = attachment.resource_id
        for vpc in region_topology.vpcs:
            if vpc.id == attachment.resource_id:
                display_name = vpc.name or vpc.id
                break
        att_label = f"{display_name}\n[{attachment.resource_type.value}]\n{attachment.state}"
        cells += _container_cell(
            att_id, att_label, ax, ay, SUBNET_W, SUBNET_H, STYLE_SUBNET_PRIVATE
        )
        cells += _edge_cell(tgw_id, att_id)

    label = f"TGW Topology — {tgw.name or tgw.id}"
    return _wrap_diagram(cells, label)


# ── Azure Virtual WAN Hub-and-Spoke ───────────────────────────────────────


def generate_vwan_topology(vwan: AzureVWan) -> str:
    """Generate draw.io XML for an Azure Virtual WAN and all its hubs."""
    import math

    cells = ""
    count = len(vwan.hubs)

    if count == 0:
        note_id = _cell_id()
        cells += _container_cell(
            note_id,
            f"Virtual WAN {vwan.name} has no hubs.",
            40,
            80,
            360,
            60,
            "text;html=1;strokeColor=none;fillColor=#ffe6cc;align=center;",
        )
        return _wrap_diagram(cells, f"vWAN Topology — {vwan.name} (empty)")

    center_x, center_y = 500, 400
    vwan_id = _cell_id()
    vwan_label = f"vWAN: {vwan.name}\n[{vwan.sku}]"
    cells += _container_cell(
        vwan_id, vwan_label, center_x, center_y, ICON_W * 2, ICON_H, STYLE_VWAN_HUB
    )

    radius = max(300, count * 60)
    for i, hub in enumerate(vwan.hubs):
        angle = (2 * math.pi * i) / count
        hx = int(center_x + radius * math.cos(angle) - ICON_W)
        hy = int(center_y + radius * math.sin(angle) - ICON_H)
        hub_id = _cell_id()
        fw_note = " \U0001f525 AFW" if hub.azure_firewall_id else ""
        er_note = " \U0001f517 ER" if hub.express_route_gateway_id else ""
        hub_label = (
            f"{hub.name}\n"
            f"{hub.location} | {hub.address_prefix}\n"
            f"[{hub.routing_state}]{fw_note}{er_note}"
        )
        cells += _container_cell(hub_id, hub_label, hx, hy, SUBNET_W, SUBNET_H + 20, STYLE_VWAN_HUB)
        cells += _edge_cell(vwan_id, hub_id)

        for j, vnet_id_str in enumerate(hub.connected_vnet_ids[:8]):
            vnet_spoke_id = _cell_id()
            vnet_name = vnet_id_str.split("/")[-1]
            inner_radius = 120
            inner_angle = angle + (math.pi / 4 * (j - len(hub.connected_vnet_ids) / 2))
            vx = int(hx + inner_radius * math.cos(inner_angle))
            vy = int(hy + inner_radius * math.sin(inner_angle))
            cells += _container_cell(vnet_spoke_id, vnet_name, vx, vy, 120, 40, STYLE_VNET)
            cells += _edge_cell(hub_id, vnet_spoke_id)

    label = f"vWAN Topology — {vwan.name}"
    return _wrap_diagram(cells, label)
