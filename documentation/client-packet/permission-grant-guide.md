# Permission Grant Guide

> **Purpose**: Step-by-step guide to granting read-only access for the assessment.
> Client follows these steps. Assessment team does not touch your IAM.

## AWS Permissions

### Step 1 — Create the Cross-Account IAM Role

In your AWS Management Account, create an IAM role named `CNA-ReadOnly-Role`
with the following trust policy (replace `VENDOR_ACCOUNT_ID`):

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": { "AWS": "arn:aws:iam::VENDOR_ACCOUNT_ID:root" },
      "Action": "sts:AssumeRole",
      "Condition": {
        "StringEquals": { "sts:ExternalId": "<provided-by-assessment-team>" }
      }
    }
  ]
}
```

### Step 2 — Attach the Managed Policy

Attach `ReadOnlyAccess` (AWS managed) plus these additional permissions:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "network-firewall:Describe*",
        "network-firewall:List*",
        "networkmanager:Get*",
        "networkmanager:List*",
        "directconnect:Describe*",
        "shield:Describe*",
        "wafv2:Get*",
        "wafv2:List*",
        "guardduty:Get*",
        "guardduty:List*"
      ],
      "Resource": "*"
    }
  ]
}
```

### Step 3 — Enable in Member Accounts (if using Organizations)

If using AWS Organizations, deploy the same role to all member accounts
via a CloudFormation StackSet from your management account.

### Step 4 — Return the Role ARN

Provide the role ARN to your assessment team:
`arn:aws:iam::<management-account-id>:role/CNA-ReadOnly-Role`

---

## Azure Permissions

### Step 1 — Create a Service Principal

```bash
az ad sp create-for-rbac --name "CNA-ReadOnly-SP" --role Reader \
  --scopes /providers/Microsoft.Management/managementGroups/<your-root-mg>
```

### Step 2 — Add Additional Role Assignments

```bash
# Security Reader — for NSGs, Security Center
az role assignment create \
  --assignee <sp-client-id> \
  --role "Security Reader" \
  --scope /providers/Microsoft.Management/managementGroups/<root-mg>

# Network Contributor (read) — for Azure Firewall, WAF
az role assignment create \
  --assignee <sp-client-id> \
  --role "Network Contributor" \
  --scope /providers/Microsoft.Management/managementGroups/<root-mg>
```

### Step 3 — Return Credentials

Return to your assessment team:
- Tenant ID
- Service Principal Client ID
- Service Principal Client Secret (share via secure channel)

---

## Verification

Your assessment team will verify access using `cna discover` before the
engagement begins. Any blocked accounts or regions will be disclosed to you
before discovery starts — not after.
