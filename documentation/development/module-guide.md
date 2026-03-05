# Module Development Guide

## Module Directory Structure

```
cna/modules/<name>/
├── __init__.py
├── module.yaml         Required: name, version, status, depends_on, required_permissions
├── discovery/
│   ├── __init__.py
│   ├── aws_<name>.py    AWS discovery class
│   └── azure_<name>.py  Azure discovery class
├── diagrams/
│   └── (diagram generators — Phase B)
└── prompts/
    └── (AI prompt templates — Phase D)
```

## module.yaml Required Fields

```yaml
name: <slug>                        # no spaces, lowercase
version: 0.1.0
display_name: Human Readable Name
status: installed                   # installed | available_not_installed
depends_on: [network]               # list of required modules
required_permissions:
  aws:
    - service:Action
  azure:
    - Microsoft.Service/resource/read
ai_recommendations_enabled: true
framework_mappings:
  - name: Framework Name
    version: "version"
```

## Discovery Class Pattern

```python
class AWSNetworkDiscovery:
    def __init__(self, session, escalation_engine, coverage_report):
        self.session = session
        self.escalation = escalation_engine
        self.coverage = coverage_report

    def discover(self) -> dict:
        """Return observed state only. No inferences."""
        # Every blocked call -> coverage_report.regions_blocked.append(...)
        # Every critical resource -> escalation_engine.evaluate(...)
        pass
```

## Adding a New Module

1. Copy `cna/modules/network/` as a template
2. Update `module.yaml` with correct name, permissions, and `status: available_not_installed`
3. Implement discovery classes (Phase C)
4. Implement diagram generators (Phase B if applicable)
5. Add unit tests in `tests/unit/test_module_<name>.py`
6. Update `depends_on` in any modules that require it
