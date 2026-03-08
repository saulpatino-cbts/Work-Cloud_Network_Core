# CNA Platform — Deployment Map

> Version: 1.0.0 | Date: 2026-03-05
> This document is the authoritative record of what is deployed, what is pending,
> and the architectural boundary between the CNA platform and client environments.

---

## The Two Planes

This platform operates across two completely separate planes. Understanding
the boundary is critical before any engagement starts.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  CNA PLATFORM PLANE                                                         │
│  Everything the CNA operator owns, builds, and operates.                   │
│  Code lives in: saulpatinojr/MVP-Cloud_Network_Assessment                  │
│                                                                             │
│  ┌────────────────┐  ┌──────────────────────┐  ┌──────────────────────┐   │
│  │ Operator       │  │ GitHub               │  │ CNA Vendor Cloud     │   │
│  │ Workstation    │  │ (Code + CI/CD)       │  │ (Azure / AWS)        │   │
│  └────────────────┘  └──────────────────────┘  └──────────────────────┘   │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │  read-only API calls
                                   │  (STS AssumeRole / DefaultAzureCredential)
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  CNA-CLIENT PLANE                                                           │
│  The customer's existing cloud environment. CNA never writes to it.        │
│  CNA only reads topology data and produces findings against it.             │
│                                                                             │
│  ┌──────────────────────┐          ┌──────────────────────┐                │
│  │ Client AWS           │          │ Client Azure         │                │
│  │ (org + all accounts) │          │ (tenant + all subs)  │                │
│  └──────────────────────┘          └──────────────────────┘                │
└─────────────────────────────────────────────────────────────────────────────┘
```

**CNA never deploys anything into the client's cloud environment.**
The only footprint in a client environment is a read-only IAM role (AWS)
or Reader RBAC assignment (Azure) that the client provisions themselves.

---

## CNA Platform Plane — Deployment Status

### Operator Workstation

| Component | Status | Notes |
|---|---|---|
| `cna` CLI (Python package) | ✅ Code complete | Install via `pip install -e .` from repo root |
| `.env` / `az login` / `aws sso login` | ✅ Documented | See `documentation/deployment-guide.md` |
| Pre-commit hooks | ✅ Configured | `.pre-commit-config.yaml` — run `pre-commit install` once |

### GitHub

| Component | Status | Notes |
|---|---|---|
| Repository (`saulpatinojr/MVP-Cloud_Network_Assessment`) | ✅ Deployed | Active, branching strategy enforced |
| `ci.yml` — lint + test + secret scan | ✅ Active | Runs on every push to `main` / `develop` |
| `release.yml` — tag + GHCR image build | ⚠️ Pending | Needs first `v0.1.0` tag to activate |
| `cd-publish.yml` — cloud deployment | ⚠️ Pending | Needs GitHub Secrets set (see below) |
| GitHub Repository Secrets | ❌ Not yet set | `CNA_AWS_ROLE_ARN`, `CNA_AZURE_*` — see `documentation/secrets-architecture.md` |
| GHCR container image (`ghcr.io/saulpatinojr/cna`) | ❌ Not built | Created on first `release.yml` run |
| Branch protection rules (require PR + CI pass) | ⚠️ Pending | Must be set manually in repo Settings → Branches |

### Azure (CNA Vendor)

| Component | Status | Notes |
|---|---|---|
| Azure Key Vault (`cna-secrets-prod`) | ❌ Not created | See `documentation/secrets-architecture.md` → Key Vault setup |
| Azure Blob Storage (`cna-deliveries` container) | ❌ Not created | Needed for Azure delivery portal |
| Azure OpenAI deployment | ❌ Not configured | Needed for AI analysis on Azure-hosted engagements |
| Managed Identity / App Registration for OIDC | ❌ Not created | Needed for `cd-publish.yml` → Azure |
| Federated Identity Credential on App Registration | ❌ Not created | Needed for OIDC token exchange |

### AWS Vendor Account

| Component | Status | Notes |
|---|---|---|
| S3 Bucket (`cna-deliverables-prod`) | ❌ Not created | Needed for AWS delivery portal |
| SSM Parameter Store (`/cna/prod/*`) | ❌ Not created | Optional — needed for team/multi-operator setup |
| OIDC Provider (`token.actions.githubusercontent.com`) | ❌ Not created | Needed for `cd-publish.yml` → AWS |
| IAM Role (`CNA-Publish`) | ❌ Not created | Needed for CD pipeline S3 write |

---

## CNA-Client Plane — What the Client Must Provision

CNA does not deploy anything into client environments. The client provisions
read-only access that CNA uses during a discovery run and removes after delivery.

### Client AWS Environment

| Component | Who Provisions | Status Per Engagement |
|---|---|---|
| IAM Role `CNA-ReadOnly` in management account | Client (guided by `permission-grant-guide.md`) | Provisioned per engagement |
| IAM Role `CNA-ReadOnly` in each member account | Client (StackSet or manual) | Provisioned per engagement |
| Trust policy: allows CNA management account to assume | Client | Per engagement |
| ExternalId condition in trust policy | Agreed between CNA and client | Per engagement |
| IAM permissions: EC2 read, Organizations read, DX read | Client | Per engagement |

The discovery engine connects to the client management account using `STS AssumeRole`
through a role chain: operator credentials → management account role → member account role.

```
CNA Operator
  └── aws sts assume-role → CNA-ReadOnly (management account)
        └── aws sts assume-role → CNA-ReadOnly (each member account)
              └── ec2:Describe*, organizations:List*, directconnect:Describe*
```

### Client Azure Environment

| Component | Who Provisions | Status Per Engagement |
|---|---|---|
| Reader role at tenant root Management Group | Client (guided by `permission-grant-guide.md`) | Provisioned per engagement |
| Management Group Reader at tenant root | Client | Per engagement |
| Private DNS Zone Contributor read at subscription level | Client (if Private DNS in scope) | Per engagement |

The discovery engine connects using `DefaultAzureCredential` (operator `az login`
or contractor service principal) and traverses the MG hierarchy top-down.

```
CNA Operator
  └── DefaultAzureCredential
        └── Reader @ Tenant Root MG
              └── ManagementGroups.list() → Subscriptions.list()
                    └── VNets, NSGs, Firewalls, ExpressRoute, Peerings...
```

---

## Remote Connection Map

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ CNA OPERATOR WORKSTATION                                                    │
│                                                                             │
│  [cna discover aws]  ──HTTPS──►  AWS STS (sts.amazonaws.com)               │
│                                     └──► Management Account                │
│                                               └──► Member Accounts (all)   │
│                                                        └──► EC2, Orgs, DX  │
│                                                                             │
│  [cna discover azure] ──HTTPS──►  Azure ARM (management.azure.com)         │
│                                     └──► Tenant Root MG                    │
│                                               └──► All Subscriptions       │
│                                                        └──► Network APIs   │
│                                                                             │
│  [az login / DefaultAzureCredential] ──HTTPS──► Azure Key Vault            │
│  [aws sso login]                     ──HTTPS──► AWS SSM                    │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ GITHUB ACTIONS (ci.yml / cd-publish.yml)                                   │
│                                                                             │
│  [cd-publish.yml]  ──OIDC──►  AWS STS → CNA-Publish Role → S3             │
│  [cd-publish.yml]  ──OIDC──►  Azure AD → Federated → Blob Storage         │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ CLIENT BROWSER (delivery)                                                  │
│                                                                             │
│  ──HTTPS + pre-signed URL──►  S3 Bucket (time-limited, no login)           │
│  ──HTTPS + SAS token──────►  Azure Blob Container (time-limited, no login) │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## What Gets Deployed to Client Cloud — The Answer is Nothing

This is a common question from clients. The definitive answer:

| Item | Deployed to Client Cloud? | Notes |
|---|---|---|
| CNA CLI binary | No | Runs on operator workstation only |
| Docker container | No | Runs on operator workstation only |
| Any Lambda / Function | No | CNA has no serverless footprint in client cloud |
| Any VM or compute | No | CNA has no compute footprint in client cloud |
| Any storage | No | CNA writes nothing to client cloud |
| Any IAM role (CNA-created) | No | Client creates read-only role; CNA does not create it |
| Any network change | No | CNA makes zero network changes |
| Any logging configuration | No | CNA reads existing logs; does not configure them |

The only action CNA takes in a client cloud is: **read-only API calls during a discovery run**, using a role the client provisioned and controls.
