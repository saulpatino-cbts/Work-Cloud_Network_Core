"""CNA API — discovery orchestration layer.

Accepts discovery jobs from cna-web, runs the Azure discovery engine in
background tasks, maps the resulting topology to security findings, and writes
everything back to PostgreSQL.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from tempfile import mkdtemp
from typing import Any

import psycopg2
import psycopg2.extras
from fastapi import BackgroundTasks, FastAPI
from pydantic import BaseModel

# Ensure the repo root is on the path so `cna` package is importable.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from cna.core.persistence import EngagementStore
from cna.modules.network.discovery.azure_discovery import (
    AzureDiscovery,
    AzureDiscoveryOptions,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("cna-api")

DATABASE_URL = os.environ.get("DATABASE_URL", "")

app = FastAPI(title="CNA API", version="0.2.0")


# ─── DB helpers ───────────────────────────────────────────────────────────────

def _get_db():
    return psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)


def _update_job(job_id: str, **kwargs: Any) -> None:
    if not DATABASE_URL:
        return
    sets = ", ".join(f'"{k}" = %s' for k in kwargs)
    values = list(kwargs.values()) + [job_id]
    with _get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f'UPDATE "DiscoveryJob" SET {sets}, "updatedAt" = NOW() WHERE id = %s',
                values,
            )
        conn.commit()


def _insert_findings(engagement_id: str, findings: list[dict]) -> None:
    if not DATABASE_URL or not findings:
        return
    with _get_db() as conn:
        with conn.cursor() as cur:
            psycopg2.extras.execute_values(
                cur,
                """INSERT INTO "Finding"
                     (id, "engagementId", title, severity, category,
                      description, recommendation, "aiGenerated", "createdAt", "updatedAt")
                   VALUES %s
                   ON CONFLICT DO NOTHING""",
                [
                    (
                        str(uuid.uuid4()),
                        engagement_id,
                        f["title"],
                        f["severity"],
                        f["category"],
                        f["description"],
                        f.get("recommendation", ""),
                        False,
                        datetime.now(timezone.utc),
                        datetime.now(timezone.utc),
                    )
                    for f in findings
                ],
            )
        conn.commit()


def _advance_engagement_status(engagement_id: str) -> None:
    if not DATABASE_URL:
        return
    with _get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE "Engagement"
                   SET status = 'DISCOVERY', "updatedAt" = NOW()
                   WHERE id = %s AND status = 'DRAFT'""",
                (engagement_id,),
            )
        conn.commit()


# ─── Topology → Findings mapper ───────────────────────────────────────────────

# Subnets managed by Azure — don't flag missing NSG on these.
_PLATFORM_SUBNETS = {
    "GatewaySubnet",
    "AzureBastionSubnet",
    "AzureFirewallSubnet",
    "AzureFirewallManagementSubnet",
    "RouteServerSubnet",
}


def _topology_to_findings(sub_topo: dict) -> list[dict]:
    """Rule-based security checks on a single AzureSubscriptionTopology dict."""
    findings: list[dict] = []
    sub_name = sub_topo.get("subscription_name") or sub_topo.get("subscription_id", "unknown")
    sub_id = sub_topo.get("subscription_id", "unknown")

    if sub_topo.get("discovery_blocked"):
        findings.append({
            "title": f"Discovery blocked for subscription '{sub_name}'",
            "severity": "HIGH",
            "category": "Access Control",
            "description": (
                f"The service principal lacks permissions to discover subscription {sub_id}. "
                f"Reason: {sub_topo.get('block_reason', 'insufficient permissions')}. "
                "Network topology is unknown for this subscription."
            ),
            "recommendation": (
                "Assign the Reader role at the subscription scope. If NSG / route table details "
                "are required, also assign Network Contributor."
            ),
        })
        return findings

    vnets: list[dict] = sub_topo.get("vnets", [])
    firewalls: list[dict] = sub_topo.get("firewalls", [])
    app_gws: list[dict] = sub_topo.get("application_gateways", [])

    # No firewall
    if vnets and not firewalls:
        findings.append({
            "title": f"No Azure Firewall deployed in '{sub_name}'",
            "severity": "HIGH",
            "category": "Network Security",
            "description": (
                f"Subscription '{sub_name}' has {len(vnets)} VNet(s) but no Azure Firewall. "
                "Without a centralized firewall, east-west and north-south traffic is uninspected."
            ),
            "recommendation": (
                "Deploy Azure Firewall (Standard or Premium) in a hub VNet. "
                "Route spoke subnets through the firewall via UDRs. "
                "Enable Threat Intelligence in Deny mode."
            ),
        })

    for vnet in vnets:
        vnet_name = vnet.get("name", "unknown")
        location = vnet.get("location", "")
        rg = vnet.get("resource_group", "")

        # DDoS
        if not vnet.get("ddos_protection_enabled"):
            findings.append({
                "title": f"VNet '{vnet_name}' has no DDoS Protection Plan",
                "severity": "MEDIUM",
                "category": "Network Protection",
                "description": (
                    f"VNet '{vnet_name}' ({location}, RG: {rg}) has no Azure DDoS Protection Plan. "
                    "Basic DDoS protection lacks adaptive tuning and rapid response SLA."
                ),
                "recommendation": (
                    "Attach a DDoS Protection Plan to VNets hosting public-facing workloads, "
                    "especially those with App Gateways or public IPs."
                ),
            })

        # Subnets without NSG
        for subnet in vnet.get("subnets", []):
            sname = subnet.get("name", "")
            if sname in _PLATFORM_SUBNETS:
                continue
            if not subnet.get("nsg_id"):
                findings.append({
                    "title": f"Subnet '{sname}' in '{vnet_name}' has no NSG",
                    "severity": "MEDIUM",
                    "category": "Network Segmentation",
                    "description": (
                        f"Subnet '{sname}' (VNet: '{vnet_name}', {location}) has no Network Security "
                        "Group. All intra-VNet traffic to this subnet is permitted by default."
                    ),
                    "recommendation": (
                        "Attach an NSG with least-privilege inbound rules. Deny all by default, "
                        "permit only required ports from approved sources. Enable NSG Flow Logs."
                    ),
                })

        # Peering gateway transit
        for peering in vnet.get("peerings", []):
            if peering.get("allow_gateway_transit") or peering.get("use_remote_gateways"):
                findings.append({
                    "title": f"VNet peering '{peering.get('name', 'unknown')}' allows gateway transit",
                    "severity": "INFORMATIONAL",
                    "category": "Routing & Transit",
                    "description": (
                        f"Peering between '{vnet_name}' and "
                        f"'{peering.get('remote_vnet_name', 'remote VNet')}' has gateway transit "
                        "enabled. Verify this is intentional (hub-spoke) and not a misconfiguration."
                    ),
                    "recommendation": (
                        "Confirm gateway transit is required for hub-spoke architecture. "
                        "Disable on spoke-to-spoke peerings to prevent unintended routing paths."
                    ),
                })

    # Firewall threat intel
    for fw in firewalls:
        fw_name = fw.get("name", "unknown")
        if fw.get("threat_intel_mode", "Alert") != "Deny":
            findings.append({
                "title": f"Firewall '{fw_name}' threat intelligence not in Deny mode",
                "severity": "HIGH",
                "category": "Network Security",
                "description": (
                    f"Azure Firewall '{fw_name}' threat intelligence mode is "
                    f"'{fw.get('threat_intel_mode', 'Alert')}'. Known-malicious IPs are alerted "
                    "but not blocked, allowing C2 traffic to pass."
                ),
                "recommendation": (
                    "Set Threat Intelligence to Deny in the Firewall Policy. "
                    "Review alert logs first to identify legitimate traffic before switching."
                ),
            })

    # AppGateway WAF
    for agw in app_gws:
        agw_name = agw.get("name", "unknown")
        if not agw.get("waf_enabled"):
            findings.append({
                "title": f"Application Gateway '{agw_name}' has WAF disabled",
                "severity": "HIGH",
                "category": "Application Security",
                "description": (
                    f"App Gateway '{agw_name}' is deployed without WAF. "
                    "Without WAF, OWASP Top 10 attacks (SQLi, XSS, request smuggling) are not inspected."
                ),
                "recommendation": (
                    "Upgrade to WAF_v2 SKU. Enable WAF in Detection mode first, "
                    "tune false positives, then switch to Prevention with OWASP 3.2 ruleset."
                ),
            })

    return findings


# ─── Routes ───────────────────────────────────────────────────────────────────

@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "cna-api", "version": "0.2.0"}


# Keep legacy endpoints so nothing breaks
@app.post("/intake")
def intake(body: dict) -> dict:
    return {"status": "accepted"}


@app.post("/publish")
def publish(body: dict) -> dict:
    return {"status": "published"}


class TestConnectionRequest(BaseModel):
    tenant_id: str
    sp_client_id: str
    sp_client_secret: str


@app.post("/discovery/test-connection")
async def test_connection(request: TestConnectionRequest) -> dict:
    """Validate SP credentials against the Azure tenant."""
    try:
        from azure.identity import ClientSecretCredential
        from azure.mgmt.subscription import SubscriptionClient

        cred = ClientSecretCredential(
            request.tenant_id, request.sp_client_id, request.sp_client_secret
        )
        client = SubscriptionClient(cred)
        subs = list(client.subscriptions.list())
        return {
            "ok": True,
            "subscriptions": [
                {"id": s.subscription_id, "name": s.display_name} for s in subs
            ],
        }
    except Exception as exc:
        logger.warning("test-connection failed: %s", exc)
        return {"ok": False, "error": str(exc)}


class DiscoveryStartRequest(BaseModel):
    job_id: str
    engagement_id: str
    tenant_id: str | None = None
    subscription_ids: list[str] = []
    sp_client_id: str | None = None
    sp_client_secret: str | None = None  # plaintext — decrypted by web layer


@app.post("/discovery/start")
async def start_discovery(
    request: DiscoveryStartRequest, background_tasks: BackgroundTasks
) -> dict:
    if not request.tenant_id:
        return {"error": "tenant_id is required"}
    _update_job(request.job_id, status="RUNNING", startedAt=datetime.now(timezone.utc))
    background_tasks.add_task(_run_azure_discovery, request)
    return {"job_id": request.job_id, "status": "RUNNING"}


@app.get("/discovery/jobs/{job_id}")
def get_job_status(job_id: str) -> dict:
    if not DATABASE_URL:
        return {"error": "DATABASE_URL not configured"}
    with _get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT id, status, "startedAt", "completedAt",
                          "findingsCount", "errorMessage", "progressLog", "updatedAt"
                   FROM "DiscoveryJob" WHERE id = %s""",
                (job_id,),
            )
            row = cur.fetchone()
    if not row:
        return {"error": "job not found"}
    return dict(row)


# ─── Background discovery task ────────────────────────────────────────────────

def _run_azure_discovery(request: DiscoveryStartRequest) -> None:
    job_id = request.job_id
    engagement_id = request.engagement_id
    progress: list[str] = []

    def _log(msg: str) -> None:
        ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
        entry = f"[{ts} UTC] {msg}"
        progress.append(entry)
        logger.info("[job:%s] %s", job_id, msg)
        _update_job(job_id, progressLog=json.dumps(progress))

    try:
        _log("Initialising discovery engine…")
        tmpdir = Path(mkdtemp(prefix="cna-discovery-"))
        store = EngagementStore(data_dir=tmpdir, engagement_id=engagement_id)

        options = AzureDiscoveryOptions(
            tenant_id=request.tenant_id,  # type: ignore[arg-type]
            subscription_ids=request.subscription_ids,
            client_id=request.sp_client_id,
            client_secret=request.sp_client_secret,
        )

        _log(f"Connecting to tenant {request.tenant_id}…")
        discovery = AzureDiscovery(store, options)

        _log("Running discovery — this may take a few minutes…")
        topology = discovery.run()

        _log(f"Scanned {len(topology.subscriptions)} subscription(s).")

        all_findings: list[dict] = []
        for sub_topo in topology.subscriptions:
            sub_dict: dict[str, Any] = json.loads(sub_topo.model_dump_json())
            sub_findings = _topology_to_findings(sub_dict)
            all_findings.extend(sub_findings)
            _log(
                f"  {sub_dict.get('subscription_name') or sub_dict.get('subscription_id')} "
                f"→ {len(sub_findings)} finding(s)"
            )

        _log(f"Writing {len(all_findings)} finding(s) to database…")
        _insert_findings(engagement_id, all_findings)
        _advance_engagement_status(engagement_id)

        topology_json = topology.model_dump_json()
        _update_job(
            job_id,
            status="COMPLETED",
            completedAt=datetime.now(timezone.utc),
            findingsCount=len(all_findings),
            topologyJson=topology_json,
            progressLog=json.dumps(progress + ["Done."]),
        )

    except Exception as exc:
        logger.exception("[job:%s] discovery failed", job_id)
        _update_job(
            job_id,
            status="FAILED",
            errorMessage=str(exc),
            completedAt=datetime.now(timezone.utc),
            progressLog=json.dumps(progress),
        )
