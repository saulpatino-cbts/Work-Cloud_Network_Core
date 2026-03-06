# AI Analysis Engine Architecture

> Version: 1.0.0 | Status: ACTIVE | Date: 2026-03-05

The AI Analysis Engine consumes topology data produced by the Discovery Engine and emits a `FindingsReport` — a structured, schema-validated list of findings with severity, observed state, evidence links, and framework mappings. It does not generate recommendations; that responsibility belongs strictly to the MCP Recommendation Engine (see DD-003).

---

## Design Guarantees

| Guarantee | Enforcement |
|---|---|
| Every finding has `observed_state` (fact, not assumption) | `ObservedStateEnforcer` — regex + evidence link check before write |
| Every finding has `severity` (CRITICAL / HIGH / MEDIUM / LOW) | `Severity` enum required in `FindingSchema` |
| Every finding has at least one `framework_mapping` | `framework_mappings` min-length-1 enforced in Pydantic model |
| Findings and recommendations are written by strictly separate code paths | `analysis_engine.py` writes findings; `recommendation_engine.py` writes recommendations — no shared function |
| Duplicate findings are suppressed | Deduplication key: `{finding_id}:{resource_id}` |
| CRITICAL findings trigger escalation before analysis completes | `EscalationEngine.emit()` called synchronously on CRITICAL severity |
| `FindingsReport` written atomically to EngagementStore | `EngagementStore.write_findings_report()` (tmp-rename) |

---

## Finding Rules

### AWS Network Rules

| Rule ID | Resource | Condition | Severity |
|---|---|---|---|
| AWS-NET-001 | VPC | Flow logs disabled | HIGH |
| AWS-NET-002 | VPC | Default VPC exists in account | MEDIUM |
| AWS-NET-003 | Security Group | Ingress 0.0.0.0/0 on port 22 or 3389 | CRITICAL |
| AWS-NET-004 | Route Table | IGW attached to non-public subnet route | HIGH |
| AWS-NET-005 | Transit Gateway | Default route table association enabled | MEDIUM |
| AWS-NET-006 | Direct Connect | No redundant connection | HIGH |
| AWS-NET-007 | VPC | No VPC endpoints for S3/DynamoDB in private subnets | MEDIUM |
| AWS-NET-008 | NAT Gateway | Single NAT covering multiple AZs | MEDIUM |
| AWS-NET-009 | Network ACL | Default NACL in use (not customized) | LOW |
| AWS-NET-010 | Security Group | Egress 0.0.0.0/0 unrestricted | LOW |
| AWS-NET-011 | VPN Gateway | No VPN redundancy (single tunnel) | HIGH |

### Azure Network Rules

| Rule ID | Resource | Condition | Severity |
|---|---|---|---|
| AZ-NET-001 | VNet | No DDoS Protection Standard | HIGH |
| AZ-NET-002 | Subnet | No NSG associated | HIGH |
| AZ-NET-003 | Azure Firewall | Threat Intelligence mode = Alert (not Deny) | MEDIUM |
| AZ-NET-004 | ExpressRoute | No redundant circuit | HIGH |
| AZ-NET-005 | VNet Peering | `allowGatewayTransit` misconfiguration | HIGH |
| AZ-NET-006 | VNet | No flow logs (NSG flow logs disabled) | HIGH |
| AZ-NET-007 | Subnet | Service endpoints not scoped to specific subnets | MEDIUM |

---

## MCP Recommendation Engine (DD-003)

Recommendations are sourced exclusively from vendor MCP servers. The analysis engine emits findings; the recommendation engine queries MCP servers for corresponding remediation guidance. They share no code path.

| Platform | MCP Server | Connection |
|---|---|---|
| AWS | `awslabs/mcp` (AWS MCP Server) | `aws_mcp_client.py` |
| Azure | Microsoft Azure MCP Server | `azure_mcp_client.py` |

The `mcp_router.py` selects the correct client based on the finding's `platform` field. MCP calls are made after all findings are written — never during finding generation.

---

## CLI Entry Point

```bash
cna analyze --engagement-id <id> [--aws] [--azure] [--dry-run]
```

Output: `engagements/{id}/reports/findings/findings_report.json`

Rich progress bar shows per-account/subscription analysis progress. Estimated time remaining is displayed for runs with more than 10 topology files.
