# Diagram Generation — Phase B (TOP PRIORITY)

## Diagram Types

| Diagram | Generator | Module | Phase |
|---|---|---|---|
| VPC topology | draw.io (n2g) | network | B |
| VNet topology | draw.io (n2g) | network | B |
| Account/subscription hierarchy | Mermaid | network | B |
| Security overlay | draw.io | security | B |
| Traffic flow | draw.io | security | B |
| Trust boundaries | draw.io + Mermaid | security | B |
| TGW / Virtual WAN topology | draw.io (n2g) | network | B |
| Landing zone architecture | Mermaid | landingzone | B |
| Zero Trust radar chart | Chart.js (HTML) | zerotrust | D |

## Output Formats

All diagram types produce all four formats:

```
.drawio  →  source file (hand-editable in draw.io desktop/web)
.svg     →  vector, lossless scaling, embed in reports
.png     →  raster, for PowerPoint/Word
.pdf     →  print-ready
```

## Export Pipeline

```
discovered topology dict
      |
      v
cna/diagram_engine/drawio_generator.py
      |  (.drawio XML string)
      v
cna/diagram_engine/export_pipeline.py
      |  (drawio CLI: .drawio -> .svg)
      |  (cairosvg: .svg -> .png)
      |  (reportlab: .png -> .pdf)
      v
output/diagrams/<client>/<region>/<type>.*
```

## Key Libraries

- `n2g` — Network to Graph, converts topology data to draw.io XML shapes
- `diagrams` — Python diagrams with native AWS + Azure provider icons
- `drawio-diagram-generator` — programmatic draw.io XML
- `cairosvg` — SVG to PNG conversion (installed via Dockerfile)
- Mermaid — embedded in portal HTML and Markdown reports

## First Implementation Target

`cna/diagram_engine/drawio_generator.py` with the `vpc_topology` diagram type.
This is the first real code written in Phase B.

## Data Contract

Diagram generators accept a standardized topology dict output by discovery:

```python
# Example VPC topology input
{
  "account_id": "123456789012",
  "region": "us-east-1",
  "vpcs": [
    {
      "id": "vpc-abc123",
      "cidr": "10.0.0.0/16",
      "name": "prod-vpc",
      "subnets": [
        {"id": "subnet-abc", "cidr": "10.0.1.0/24", "az": "us-east-1a", "type": "private"},
        {"id": "subnet-def", "cidr": "10.0.2.0/24", "az": "us-east-1b", "type": "public"}
      ],
      "internet_gateway": "igw-abc",
      "nat_gateways": ["nat-abc"],
      "route_tables": [...]
    }
  ],
  "transit_gateways": [...],
  "vpc_peering": [...]
}
```
