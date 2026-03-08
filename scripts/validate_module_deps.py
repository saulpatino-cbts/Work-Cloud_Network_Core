"""CI script: validate all module.yaml depends_on reference installed modules.

Closes TODO_PhaseA: Module depends_on not enforced.
Runs in CI (module-dependency-check job) and can be run locally.

Exit 0: all dependencies satisfied.
Exit 1: one or more modules depend on an uninstalled module — blocks merge.
"""
import sys
from pathlib import Path

import yaml

MODULES_DIR = Path("cna/modules")


def load_installed_modules() -> dict[str, dict]:
    installed = {}
    for module_yaml in MODULES_DIR.rglob("module.yaml"):
        with open(module_yaml) as f:
            data = yaml.safe_load(f)
        module_name = data.get("name")
        if data.get("status") == "installed" and module_name:
            installed[module_name] = data
    return installed


def validate() -> bool:
    installed = load_installed_modules()
    all_modules = {}
    for module_yaml in MODULES_DIR.rglob("module.yaml"):
        with open(module_yaml) as f:
            data = yaml.safe_load(f)
        if name := data.get("name"):
            all_modules[name] = data

    errors = []
    for name, data in all_modules.items():
        if data.get("status") != "installed":
            continue
        for dep in data.get("depends_on", []):
            if dep not in installed:
                errors.append(
                    f"ERROR: Module '{name}' depends on '{dep}' "
                    f"but '{dep}' is not installed."
                )

    if errors:
        for e in errors:
            print(e, file=sys.stderr)
        print(f"\n{len(errors)} dependency error(s) found. Fix module.yaml files.", file=sys.stderr)
        return False

    print(f"OK: {len(installed)} installed modules, all dependencies satisfied.")
    return True


if __name__ == "__main__":
    sys.exit(0 if validate() else 1)
