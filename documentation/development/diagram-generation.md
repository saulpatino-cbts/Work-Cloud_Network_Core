# Diagram Generation — Phase B

> Version: 1.1.0 | Updated: 2026-03-05 | Status: ACTIVE

---

## Three Output Formats

| Format | Tool | Use Case | Phase |
|---|---|---|---|
| `.drawio` | draw.io XML generator | Client-editable deliverable, relationship diagrams | B ✅ |
| `.mmd` → `.svg` | Mermaid CLI (`mmdc`) | Portal HTML, Markdown reports, GitHub rendering | B ✅ |
| `.png` | Mingrammer `diagrams` | Code-driven, reproducible, AWS/Azure icon fidelity | B ✅ |

---

## Generating Diagrams

### Local (with draw.io CLI installed)
```bash
# Generate all diagrams for an engagement
cna diagram generate --engagement-id acme-20260305-a3f2

# Skip raster export (XML only — for dev/testing)
CNA_SKIP_RASTER=true cna diagram generate --engagement-id acme-20260305-a3f2

# Preview Mermaid in browser
cna diagram preview --type account-hierarchy
```

### Docker (recommended)
```bash
# Full export chain: .drawio → .svg → .png → .pdf
docker-compose run cna cna diagram generate --engagement-id acme-20260305-a3f2
```

---

## File Naming Convention

All diagram files follow this pattern:
```
{engagement_id}-{platform}-{diagram_type}-{scope}-{region}.{ext}
```

Examples:
```
acme-20260305-a3f2-aws-vpc-topology-123456789012-us-east-1.drawio
acme-20260305-a3f2-azure-vnet-topology-sub-a1b2c3d4.svg
acme-20260305-a3f2-aws-account-hierarchy.mmd
```

See `cna/diagram_engine/naming.py` for the `diagram_filename()` function.

---

## Diagram Type Matrix

| Diagram Type | Generator | Input Model | Output Formats |
|---|---|---|---|
| `vpc-topology` | `drawio_generator.generate_vpc_topology()` | `AWSRegionTopology` | .drawio, .svg, .png |
| `vnet-topology` | `drawio_generator.generate_vnet_topology()` | `AzureSubscriptionTopology` | .drawio, .svg, .png |
| `tgw-topology` | `drawio_generator.generate_tgw_topology()` | `TransitGateway` + `AWSRegionTopology` | .drawio, .svg, .png |
| `vwan-topology` | `drawio_generator.generate_vwan_topology()` | `AzureVWan` | .drawio, .svg, .png |
| `account-hierarchy` | `mermaid_generator.generate_aws_account_hierarchy()` | `AWSTopology` | .mmd, .svg |
| `mg-hierarchy` | `mermaid_generator.generate_azure_mg_hierarchy()` | `AzureTopology` | .mmd, .svg |
| `landing-zone` | `mermaid_generator.generate_landing_zone_diagram()` | `dict` (design notes) | .mmd, .svg |
| `aws-infra` | `diagrams_generator.generate_aws_vpc_diagram()` | `AWSRegionTopology` | .png |
| `azure-infra` | `diagrams_generator.generate_azure_vnet_diagram()` | `AzureSubscriptionTopology` | .png |

---

## Schema Version

Topology schema is versioned in `cna/core/topology_schema.py`:
```python
TOPOLOGY_SCHEMA_VERSION = "1.1.0"
```

Current schema (v1.1.0) adds:
- AWS: `SecurityGroup`, `NACL`, `VpnGateway`, `NetworkFirewallPolicy`
- Azure: `AzureFirewall`, `ApplicationGateway`, `PrivateDnsZone`, `ExpressRouteCircuit`

---

## Export Pipeline Configuration

| Env Var | Default | Description |
|---|---|---|
| `CNA_SKIP_RASTER` | `false` | Skip SVG/PNG/PDF export (XML only) |
| `CNA_DIAGRAM_DPI` | `150` | PNG output DPI |
| `CNA_DIAGRAM_MAX_PX` | `4096` | Max PNG dimension in pixels |

---

## DPI and Size Configuration

The export pipeline computes PNG scale dynamically:
```
scale = min(dpi / 96, max_dimension_px / max(svg_width, svg_height))
```

Default `dpi=150` produces presentation-quality PNGs. For large diagrams
(20+ subnets), the `max_dimension_px=4096` cap prevents PPTX embed issues.
For print-quality output: `CNA_DIAGRAM_DPI=300 CNA_DIAGRAM_MAX_PX=8192`.
