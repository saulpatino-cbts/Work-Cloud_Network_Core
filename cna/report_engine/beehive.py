"""Obsidian beehive — network-flow map (BUILD-02 beehive mode).

Builds a normalized network graph (nodes + edges) from the discovered topology
and renders it as an Obsidian vault plus a machine-readable graph.json. The
beehive shows **ports, IPs, networks and the connections between them** — the
network flow/mapping view — as opposed to the findings vault
(`obsidian_vault.py`).

Multi-source by construction: it consumes `AWSTopology` / `AzureTopology`, which
`EngagementStore` reassembles from ALL of a customer's discovery checkpoints
(every subscription/account, including ones added by the batch offline import),
so one customer's whole estate appears in one graph. Single customer per
appliance, so there is no cross-customer concern (see the spec).

Observed state only (DD-002): edges reflect configured/discovered connectivity
(peerings, routes, security-group/NSG allowances). An edge only asserts live
reachability when it came from a Reachability Analyzer result (BUILD-01 C6).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from pydantic import BaseModel, Field

from cna.report_engine.obsidian_common import slug, wikilink, write_note, yaml_scalar, zip_tree

logger = logging.getLogger("cna.report.beehive")


# ── graph model (also the shape of graph.json, R2.2) ────────────────────────


class GraphNode(BaseModel):
    id: str
    kind: str  # network | subnet | node | gateway | endpoint
    name: str = ""
    source_id: str = ""  # subscription / tenant / account id (R3 attribution)
    cloud: str = ""  # aws | azure
    cidrs: list[str] = Field(default_factory=list)
    ips: list[str] = Field(default_factory=list)


class GraphEdge(BaseModel):
    src: str
    dst: str
    kind: str  # peering | route | tgw | vpn | sg-allow | nsg-allow | contains | reachable
    ports: list[str] = Field(default_factory=list)  # "tcp/443", "-1/all"
    cidr: str = ""
    source_id: str = ""
    observed: bool = True  # reachable edges are the only live-verified ones


class NetworkGraph(BaseModel):
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)

    def add_node(self, node: GraphNode) -> None:
        if not any(n.id == node.id for n in self.nodes):
            self.nodes.append(node)

    def add_edge(self, edge: GraphEdge) -> None:
        self.edges.append(edge)


# ── builders ────────────────────────────────────────────────────────────────


def _port_label(protocol: str, from_port, to_port) -> str:
    proto = (protocol or "-1").lower()
    if proto in ("-1", "all", ""):
        return "-1/all"
    if from_port is None and to_port is None:
        return f"{proto}/all"
    if from_port == to_port or to_port is None:
        return f"{proto}/{from_port}"
    return f"{proto}/{from_port}-{to_port}"


def _aws_node_id(account_id: str, resource_id: str) -> str:
    return f"aws:{account_id}:{resource_id}"


def _azure_node_id(sub_id: str, resource_id: str) -> str:
    # Azure resource ids are long ARM paths; use the leaf for readability.
    leaf = resource_id.rsplit("/", 1)[-1] if resource_id else resource_id
    return f"azure:{sub_id}:{leaf}"


def _build_aws(graph: NetworkGraph, aws) -> None:
    for region in getattr(aws, "regions", []) or []:
        acct = region.account_id
        for vpc in region.vpcs:
            vpc_nid = _aws_node_id(acct, vpc.id)
            graph.add_node(
                GraphNode(
                    id=vpc_nid, kind="network", name=vpc.name or vpc.id, source_id=acct,
                    cloud="aws", cidrs=[vpc.cidr, *vpc.secondary_cidrs],
                )
            )
            for subnet in vpc.subnets:
                sn_nid = _aws_node_id(acct, subnet.id)
                graph.add_node(
                    GraphNode(id=sn_nid, kind="subnet", name=subnet.name or subnet.id,
                              source_id=acct, cloud="aws", cidrs=[subnet.cidr])
                )
                graph.add_edge(GraphEdge(src=vpc_nid, dst=sn_nid, kind="contains", source_id=acct))
            for nat in vpc.nat_gateways:
                ng = _aws_node_id(acct, nat.id)
                graph.add_node(
                    GraphNode(id=ng, kind="gateway", name=nat.name or nat.id, source_id=acct,
                              cloud="aws", ips=[nat.public_ip] if getattr(nat, "public_ip", None) else [])
                )
                graph.add_edge(GraphEdge(src=vpc_nid, dst=ng, kind="contains", source_id=acct))
            # security-group allowances -> sg-allow edges carrying ports + CIDRs
            for sg in vpc.security_groups:
                for rule in sg.rules:
                    if rule.direction != "ingress":
                        continue
                    port = _port_label(rule.protocol, rule.from_port, rule.to_port)
                    for cidr in rule.cidr_ranges or []:
                        graph.add_edge(
                            GraphEdge(src=f"cidr:{cidr}", dst=vpc_nid, kind="sg-allow",
                                      ports=[port], cidr=cidr, source_id=acct)
                        )
                        graph.add_node(GraphNode(id=f"cidr:{cidr}", kind="endpoint", name=cidr, cidrs=[cidr]))
                    if rule.source_sg_id:
                        graph.add_edge(
                            GraphEdge(src=_aws_node_id(acct, rule.source_sg_id), dst=vpc_nid,
                                      kind="sg-allow", ports=[port], source_id=acct)
                        )
            # peerings (incl. cross-account) -> peering edges
            for p in vpc.peering_connections:
                src = _aws_node_id(p.requester_account_id, p.requester_vpc_id)
                dst = _aws_node_id(p.accepter_account_id, p.accepter_vpc_id)
                graph.add_edge(GraphEdge(src=src, dst=dst, kind="peering", source_id=acct))
        # TGW route analysis (BUILD-01 C3), when present
        for tra in getattr(region, "tgw_route_analyses", []) or []:
            tgw_nid = _aws_node_id(acct, tra.transit_gateway_id)
            graph.add_node(GraphNode(id=tgw_nid, kind="gateway", name=tra.transit_gateway_id,
                                     source_id=acct, cloud="aws"))
            for route in tra.routes:
                if route.attachment_id:
                    graph.add_edge(
                        GraphEdge(src=tgw_nid, dst=_aws_node_id(acct, route.attachment_id),
                                  kind="tgw", cidr=route.destination_cidr, source_id=acct)
                    )
        # reachability (BUILD-01 C6) -> the only live-verified edges
        for rp in getattr(region, "reachability_paths", []) or []:
            if rp.reachable:
                graph.add_edge(
                    GraphEdge(src=_aws_node_id(acct, rp.source), dst=_aws_node_id(acct, rp.destination),
                              kind="reachable", source_id=acct, observed=True)
                )


def _build_azure(graph: NetworkGraph, azure) -> None:
    for sub in getattr(azure, "subscriptions", []) or []:
        sid = sub.subscription_id
        for vnet in getattr(sub, "vnets", []) or []:
            vnet_nid = _azure_node_id(sid, vnet.id)
            graph.add_node(
                GraphNode(id=vnet_nid, kind="network", name=vnet.name, source_id=sid,
                          cloud="azure", cidrs=list(vnet.address_space or []))
            )
            for subnet in vnet.subnets:
                sn_nid = _azure_node_id(sid, subnet.id)
                graph.add_node(
                    GraphNode(id=sn_nid, kind="subnet", name=subnet.name, source_id=sid,
                              cloud="azure", cidrs=[subnet.address_prefix] if subnet.address_prefix else [])
                )
                graph.add_edge(GraphEdge(src=vnet_nid, dst=sn_nid, kind="contains", source_id=sid))
            for p in getattr(vnet, "peerings", []) or []:
                dst_sid = p.remote_subscription_id or sid
                dst = _azure_node_id(dst_sid, p.remote_vnet_id)
                graph.add_edge(GraphEdge(src=vnet_nid, dst=dst, kind="peering", source_id=sid))
        # NSG allowances -> nsg-allow edges with ports (when the sub exposes them)
        for nsg in getattr(sub, "nsgs", []) or []:
            for rule in getattr(nsg, "rules", []) or []:
                if getattr(rule, "direction", "").lower() not in ("inbound", "ingress"):
                    continue
                proto = getattr(rule, "protocol", "-1")
                port = getattr(rule, "destination_port_range", None) or getattr(rule, "to_port", None)
                label = f"{str(proto).lower()}/{port}" if port else f"{str(proto).lower()}/all"
                graph.add_edge(
                    GraphEdge(src=f"nsg:{getattr(nsg, 'id', getattr(nsg, 'name', 'nsg'))}",
                              dst=f"azure:{sid}", kind="nsg-allow", ports=[label], source_id=sid)
                )


def build_network_graph(aws=None, azure=None) -> NetworkGraph:
    """Build one NetworkGraph spanning all supplied topology (AWS and/or Azure).

    Multi-source: every subscription/account in the topologies contributes nodes
    and edges, each tagged with its source_id so the graph unifies one customer's
    estate (R3).
    """
    graph = NetworkGraph()
    if aws is not None:
        _build_aws(graph, aws)
    if azure is not None:
        _build_azure(graph, azure)
    _complete_edge_endpoints(graph)
    return graph


def _complete_edge_endpoints(graph: NetworkGraph) -> None:
    """Ensure every edge endpoint has a node.

    An edge can reference a resource that was not itself discovered — a peering
    to a VPC/VNet in an account/subscription outside this scan, a source
    security group, an NSG id. Those are real connectivity facts, so rather than
    drop them (losing the edge) we add a lightweight "external" node so the graph
    is complete and every wiki-link resolves. The node is labeled external so the
    beehive shows the connection goes somewhere not scanned.
    """
    known = {n.id for n in graph.nodes}
    for e in graph.edges:
        for endpoint in (e.src, e.dst):
            if endpoint not in known:
                # Derive a readable name and any source id embedded in the id.
                parts = endpoint.split(":")
                source_id = parts[1] if len(parts) >= 3 and parts[0] in ("aws", "azure") else ""
                cloud = parts[0] if parts and parts[0] in ("aws", "azure") else ""
                graph.add_node(
                    GraphNode(
                        id=endpoint, kind="external", name=parts[-1] if parts else endpoint,
                        source_id=source_id, cloud=cloud,
                    )
                )
                known.add(endpoint)


# ── renderer ────────────────────────────────────────────────────────────────


class BeehiveRenderer:
    """Renders a NetworkGraph as an Obsidian vault + graph.json, then zips it."""

    def render(self, graph: NetworkGraph, output_path: Path) -> Path:
        output_path = Path(output_path)
        vault = output_path.with_suffix("")
        vault.mkdir(parents=True, exist_ok=True)

        self._write_readme(vault, graph)
        self._write_network_notes(vault, graph)
        self._write_connection_notes(vault, graph)
        # machine-readable graph (R2.2)
        (vault / "graph.json").write_text(
            json.dumps(graph.model_dump(), indent=2), encoding="utf-8"
        )
        zip_path = zip_tree(vault, output_path)
        logger.info("Beehive vault written: %s (zipped %s)", vault, zip_path)
        return zip_path

    def _write_readme(self, vault: Path, graph: NetworkGraph) -> None:
        sources = sorted({n.source_id for n in graph.nodes if n.source_id})
        lines = [
            "# Network Beehive — flow & mapping",
            "",
            "Open this folder in [Obsidian](https://obsidian.md) and use the graph view to see "
            "networks, nodes and the connections between them. `graph.json` is the same data in "
            "machine-readable form.",
            "",
            f"- Nodes: {len(graph.nodes)}",
            f"- Connections: {len(graph.edges)}",
            f"- Sources (subscriptions/accounts): {', '.join(sources) if sources else '(none)'}",
            "",
            "## Networks",
            "",
        ]
        for n in graph.nodes:
            if n.kind == "network":
                lines.append(f"- {wikilink(slug(n.id), n.name or n.id)} "
                             f"({n.cloud}, {n.source_id}) {', '.join(n.cidrs)}")
        write_note(vault / "README.md", lines)

    def _write_network_notes(self, vault: Path, graph: NetworkGraph) -> None:
        d = vault / "Networks"
        nd = vault / "Nodes"
        edges_by_src: dict[str, list[GraphEdge]] = {}
        for e in graph.edges:
            edges_by_src.setdefault(e.src, []).append(e)
        for node in graph.nodes:
            lines = [
                "---",
                f"kind: {node.kind}",
                f"cloud: {node.cloud}",
                f"source_id: {yaml_scalar(node.source_id)}",
            ]
            if node.cidrs:
                lines.append("cidrs:")
                lines += [f"  - {c}" for c in node.cidrs]
            if node.ips:
                lines.append("ips:")
                lines += [f"  - {ip}" for ip in node.ips]
            lines += ["---", "", f"# {node.name or node.id}", ""]
            outgoing = edges_by_src.get(node.id, [])
            if outgoing:
                lines += ["## Connections from here", ""]
                for e in outgoing:
                    ports = f" ports: {', '.join(e.ports)}" if e.ports else ""
                    lines.append(f"- {e.kind} -> {wikilink(slug(e.dst))}{ports}")
                lines.append("")
            target = (d if node.kind in ("network", "subnet") else nd)
            write_note(target / f"{slug(node.id)}.md", lines)

    def _write_connection_notes(self, vault: Path, graph: NetworkGraph) -> None:
        d = vault / "Connections"
        for i, e in enumerate(graph.edges):
            # Skip plain containment edges as standalone notes (they are implicit
            # in the network notes); keep the connectivity-bearing ones.
            if e.kind == "contains":
                continue
            stem = slug(f"{e.kind}-{e.src}-{e.dst}-{i}")
            lines = [
                "---",
                f"kind: {e.kind}",
                f"observed: {str(e.observed).lower()}",
                f"source_id: {yaml_scalar(e.source_id)}",
                "---",
                "",
                f"# {e.kind}: {e.src} -> {e.dst}",
                "",
                f"- From: {wikilink(slug(e.src))}",
                f"- To: {wikilink(slug(e.dst))}",
            ]
            if e.ports:
                lines.append(f"- Ports: {', '.join(e.ports)}")
            if e.cidr:
                lines.append(f"- CIDR: {e.cidr}")
            if e.kind == "reachable":
                lines.append("- **Live-verified reachable** (Reachability Analyzer)")
            write_note(d / f"{stem}.md", lines)
