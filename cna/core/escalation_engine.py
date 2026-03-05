"""Real-time critical finding escalation.

DD-016: Fires during DISCOVERY — not during analysis.
Critical findings are escalated immediately, not held until final report.
"""
from datetime import datetime

CRITICAL_TRIGGERS_AWS = [
    {"service": "ec2", "check": "sg_ingress_0000_port_22",   "title": "SSH exposed to internet"},
    {"service": "ec2", "check": "sg_ingress_0000_port_3389", "title": "RDP exposed to internet"},
    {"service": "ec2", "check": "sg_ingress_0000_all_ports", "title": "All ports exposed to internet"},
    {"service": "nfw", "check": "firewall_default_allow",    "title": "Network Firewall default allow"},
]

CRITICAL_TRIGGERS_AZURE = [
    {"service": "nsg", "check": "any_any_allow", "title": "NSG allows any-to-any traffic"},
    {"service": "afw", "check": "idps_off",      "title": "Azure Firewall IDPS disabled"},
]


class CriticalFindingEscalationEngine:
    def __init__(self, notifier=None):
        self.notifier = notifier  # Teams/email notifier injected at runtime
        self.critical_log: list = []

    def evaluate(self, resource: dict, service: str, platform: str) -> None:
        """Called per-resource during discovery — not during analysis."""
        triggers = CRITICAL_TRIGGERS_AWS if platform == "aws" else CRITICAL_TRIGGERS_AZURE
        for trigger in triggers:
            if trigger["service"] == service and self._matches(resource, trigger["check"]):
                self._escalate(resource, trigger)

    def _matches(self, resource: dict, check: str) -> bool:
        # TODO: Phase C — implement per-check matching logic
        return False

    def _escalate(self, resource: dict, trigger: dict) -> None:
        event = {
            "trigger": trigger,
            "resource_id": resource.get("id") or resource.get("ResourceId"),
            "at": datetime.utcnow().isoformat(),
        }
        self.critical_log.append(event)
        if self.notifier:
            self.notifier.send_critical_alert(event)
