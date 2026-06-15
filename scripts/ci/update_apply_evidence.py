"""
Update deployment manifest after Terraform apply completes.

Reads from environment variables:
  MANIFEST_PATH                   — path to deployment-manifest.json
  FRONTDOOR_ENDPOINT_HOST_NAME    — terraform output value
  FRONTDOOR_PROFILE_ID            — terraform output value
  FRONTDOOR_ENDPOINT_ID           — terraform output value
  FRONTDOOR_ORIGIN_GROUP_ID       — terraform output value
  FRONTDOOR_ROUTE_ID              — terraform output value
  FRONTDOOR_CUSTOM_DOMAIN_ID      — terraform output value (optional)
  FRONTDOOR_SECRET_ID             — terraform output value (optional)
  NEXTAUTH_URL                    — derived runtime public URL
"""

import json
import os
from pathlib import Path

manifest = Path(os.environ["MANIFEST_PATH"])

with manifest.open() as f:
    data = json.load(f)

data["validation_checks"]["terraform_apply"] = "passed"
data["platform_context"] = {
    "frontdoor_endpoint_host_name": os.environ.get("FRONTDOOR_ENDPOINT_HOST_NAME", ""),
    "nextauth_url": os.environ.get("NEXTAUTH_URL", ""),
    "frontdoor_profile_id": os.environ.get("FRONTDOOR_PROFILE_ID", ""),
    "frontdoor_endpoint_id": os.environ.get("FRONTDOOR_ENDPOINT_ID", ""),
    "frontdoor_origin_group_id": os.environ.get("FRONTDOOR_ORIGIN_GROUP_ID", ""),
    "frontdoor_route_id": os.environ.get("FRONTDOOR_ROUTE_ID", ""),
    "frontdoor_custom_domain_id": os.environ.get("FRONTDOOR_CUSTOM_DOMAIN_ID", ""),
    "frontdoor_secret_id": os.environ.get("FRONTDOOR_SECRET_ID", ""),
}

with manifest.open("w") as f:
    json.dump(data, f, indent=2)
    f.write("\n")

print(f"Updated manifest: {manifest}")
print("  terraform_apply = passed")
print(
    f"  frontdoor_endpoint_host_name = {data['platform_context']['frontdoor_endpoint_host_name']}"
)
print(f"  nextauth_url = {data['platform_context']['nextauth_url']}")
