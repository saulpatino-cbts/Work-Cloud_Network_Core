"""Unit tests for cna.report_engine.beehive (BUILD-02 beehive mode).

Synthetic topology only. Covers graph building (nodes/edges/ports, cross-source
peering), the renderer (note tree, graph.json round-trip, wiki-link audit),
pipeline modes, and observed-only edges (no reachable edge without a C6 result).
"""

from __future__ import annotations

import json
import re
import zipfile

from cna.core.topology_schema import (
    VPC,
    AWSReachabilityPath,
    AWSRegionTopology,
    AWSTopology,
    AzureSubscriptionTopology,
    AzureTopology,
    PeeringState,
    SecurityGroup,
    SecurityGroupRule,
    Subnet,
    VNet,
    VNetPeering,
    VpcPeeringConnection,
)
from cna.report_engine.beehive import (
    BeehiveRenderer,
    NetworkGraph,
    build_network_graph,
)


def _aws_topology() -> AWSTopology:
    sg = SecurityGroup(
        id="sg-1",
        vpc_id="vpc-a",
        rules=[
            SecurityGroupRule(
                direction="ingress",
                protocol="tcp",
                from_port=443,
                to_port=443,
                cidr_ranges=["10.0.0.0/8"],
            )
        ],
    )
    vpc = VPC(
        id="vpc-a",
        name="prod",
        cidr="10.0.0.0/16",
        subnets=[Subnet(id="subnet-1", cidr="10.0.1.0/24", az="us-east-1a")],
        security_groups=[sg],
        peering_connections=[
            VpcPeeringConnection(
                id="pcx-1",
                requester_vpc_id="vpc-a",
                requester_account_id="111111111111",
                requester_region="us-east-1",
                accepter_vpc_id="vnet-x",
                accepter_account_id="222222222222",
                accepter_region="us-east-1",
                state=PeeringState.ACTIVE,
            )
        ],
    )
    region = AWSRegionTopology(account_id="111111111111", region="us-east-1", vpcs=[vpc])
    return AWSTopology(engagement_id="eng", regions=[region])


def _azure_topology() -> AzureTopology:
    vnet = VNet(
        id="/subscriptions/sub-1/vnet-y",
        name="hub",
        location="eastus",
        resource_group="rg",
        subscription_id="sub-1",
        address_space=["10.1.0.0/16"],
        peerings=[
            VNetPeering(
                id="peer-1",
                name="to-spoke",
                remote_vnet_id="/subscriptions/sub-2/vnet-z",
                remote_subscription_id="sub-2",
                peering_state="Connected",
                allow_forwarded_traffic=False,
                allow_gateway_transit=False,
                use_remote_gateways=False,
            )
        ],
    )
    sub = AzureSubscriptionTopology(
        subscription_id="sub-1", subscription_name="s", tenant_id="t", vnets=[vnet]
    )
    return AzureTopology(engagement_id="eng", tenant_id="t", subscriptions=[sub])


class TestGraphBuild:
    def test_nodes_and_containment(self):
        g = build_network_graph(aws=_aws_topology())
        ids = {n.id for n in g.nodes}
        assert "aws:111111111111:vpc-a" in ids
        assert "aws:111111111111:subnet-1" in ids
        contains = [e for e in g.edges if e.kind == "contains"]
        assert any(e.dst == "aws:111111111111:subnet-1" for e in contains)

    def test_sg_allow_edge_carries_ports_and_cidr(self):
        g = build_network_graph(aws=_aws_topology())
        sgedges = [e for e in g.edges if e.kind == "sg-allow"]
        assert sgedges
        e = sgedges[0]
        assert e.ports == ["tcp/443"]
        assert e.cidr == "10.0.0.0/8"

    def test_cross_account_peering_edge(self):
        g = build_network_graph(aws=_aws_topology())
        peers = [e for e in g.edges if e.kind == "peering"]
        assert any(
            e.src == "aws:111111111111:vpc-a" and e.dst == "aws:222222222222:vnet-x" for e in peers
        )

    def test_azure_cross_subscription_peering(self):
        g = build_network_graph(azure=_azure_topology())
        peers = [e for e in g.edges if e.kind == "peering"]
        # edge from sub-1's vnet to sub-2's remote vnet (cross-source)
        assert any(
            e.src.startswith("azure:sub-1:") and e.dst.startswith("azure:sub-2:") for e in peers
        )

    def test_mixed_cloud_in_one_graph(self):
        g = build_network_graph(aws=_aws_topology(), azure=_azure_topology())
        clouds = {n.cloud for n in g.nodes if n.cloud}
        assert clouds == {"aws", "azure"}
        sources = {n.source_id for n in g.nodes if n.source_id}
        # unifies multiple sources in one graph (R3)
        assert {"111111111111", "sub-1"}.issubset(sources)


class TestObservedOnly:
    def test_no_reachable_edge_without_c6_result(self):
        g = build_network_graph(aws=_aws_topology())
        assert not any(e.kind == "reachable" for e in g.edges)

    def test_reachable_edge_only_from_c6(self):
        aws = _aws_topology()
        aws.regions[0].reachability_paths = [
            AWSReachabilityPath(
                name="web->rds", source="eni-a", destination="eni-b", reachable=True
            )
        ]
        g = build_network_graph(aws=aws)
        reach = [e for e in g.edges if e.kind == "reachable"]
        assert len(reach) == 1
        assert reach[0].observed is True


class TestRenderer:
    def test_tree_and_graph_json_roundtrip(self, tmp_path):
        g = build_network_graph(aws=_aws_topology(), azure=_azure_topology())
        zip_path = tmp_path / "beehive.zip"
        BeehiveRenderer().render(g, zip_path)
        vault = zip_path.with_suffix("")
        assert (vault / "README.md").is_file()
        assert (vault / "graph.json").is_file()
        assert (vault / "Networks").is_dir()
        assert (vault / "Connections").is_dir()
        # graph.json round-trips to the same graph
        loaded = NetworkGraph(**json.loads((vault / "graph.json").read_text()))
        assert len(loaded.nodes) == len(g.nodes)
        assert len(loaded.edges) == len(g.edges)

    def test_zip_contains_graph_json(self, tmp_path):
        g = build_network_graph(aws=_aws_topology())
        zip_path = tmp_path / "beehive.zip"
        BeehiveRenderer().render(g, zip_path)
        with zipfile.ZipFile(zip_path) as zf:
            assert any(n.endswith("graph.json") for n in zf.namelist())

    def test_wikilinks_resolve(self, tmp_path):
        g = build_network_graph(aws=_aws_topology(), azure=_azure_topology())
        zip_path = tmp_path / "beehive.zip"
        BeehiveRenderer().render(g, zip_path)
        vault = zip_path.with_suffix("")
        stems = {p.stem for p in vault.rglob("*.md")}
        link_re = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]")
        for md in vault.rglob("*.md"):
            for target in link_re.findall(md.read_text(encoding="utf-8")):
                assert target in stems, f"broken wiki-link [[{target}]] in {md.name}"


class TestPipelineModes:
    def _report(self, review_complete=True):
        from datetime import UTC, datetime

        from cna.core.findings_schema import FindingsReport

        return FindingsReport(
            engagement_id="eng",
            findings=[],
            total_count=0,
            critical_count=0,
            high_count=0,
            medium_count=0,
            low_count=0,
            review_complete=review_complete,
            generated_at=datetime.now(UTC).isoformat(),
        )

    def _store_with_topology(self, tmp_path):
        from cna.core.persistence import EngagementStore

        store = EngagementStore(data_dir=tmp_path, engagement_id="eng")
        store.write_discovery_checkpoint(
            "eng", "aws", "111111111111", _aws_topology().regions[0].model_dump()
        )
        return store

    def test_both_mode_emits_two_obsidian_records(self, tmp_path):
        from cna.report_engine.render_pipeline import RenderOptions, RenderPipeline

        store = self._store_with_topology(tmp_path)
        opts = RenderOptions(
            render_html_preview=False,
            render_executive=False,
            render_technical=False,
            render_pptx=False,
            render_regional_en=False,
            render_obsidian=True,
            obsidian_mode="both",
            output_dir=tmp_path / "out",
        )
        manifest = RenderPipeline(store, opts).run(self._report())
        obs = [r for r in manifest.records if r.format == "obsidian"]
        assert len(obs) == 2
        labels = {r.label for r in obs}
        assert labels == {"Obsidian Findings Vault", "Obsidian Beehive"}

    def test_beehive_without_topology_skips_cleanly(self, tmp_path):
        from cna.core.persistence import EngagementStore
        from cna.report_engine.render_pipeline import RenderOptions, RenderPipeline

        store = EngagementStore(data_dir=tmp_path, engagement_id="eng")  # no checkpoints
        opts = RenderOptions(
            render_html_preview=False,
            render_executive=False,
            render_technical=False,
            render_pptx=False,
            render_regional_en=False,
            render_obsidian=True,
            obsidian_mode="beehive",
            output_dir=tmp_path / "out",
        )
        manifest = RenderPipeline(store, opts).run(self._report())
        assert [r for r in manifest.records if r.format == "obsidian"] == []
