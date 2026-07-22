# CNA Platform — AWS Infrastructure Migration

Terraform configuration that deploys the CNA platform on AWS, mirroring the Azure infrastructure with equivalent AWS services.

## Architecture Mapping (Azure → AWS)

| Azure Service | AWS Equivalent | Resource |
|---|---|---|
| Container Apps (3 services) | ECS Fargate (3 services) | Web, API, Worker |
| Azure Front Door + WAF | CloudFront + WAF v2 | CDN + security |
| Application Load Balancer | ALB | Path-based routing |
| PostgreSQL Flexible Server | RDS PostgreSQL 16 | Database |
| Key Vault | Secrets Manager | Secret storage |
| Storage Account (Blob) | S3 | Object storage |
| Azure Firewall | Security Groups + NAT GW | Egress control |
| VNet + Subnets | VPC + Subnets | Networking |
| Managed Identity | IAM Roles | Workload identity |
| OIDC (Entra) | OIDC (GitHub → IAM) | CI/CD auth |
| Log Analytics | CloudWatch Logs | Observability |

## IAM / RBAC

The deploy role carries three assessment-level policies (equivalent to Azure's Global Reader, Security Reader, and Billing Reader):

| AWS Policy | Azure Equivalent | Purpose |
|---|---|---|
| `ReadOnlyAccess` | Global Reader | Enumerate all resources |
| `SecurityAudit` | Security Reader | Security findings |
| `AWSBillingReadOnlyAccess` | Billing Reader | Cost/usage for FinOps |

Plus a scoped write policy for Terraform to manage CNA infrastructure.

## Prerequisites

1. AWS account with permissions to create IAM roles and infrastructure
2. Terraform >= 1.9.0
3. AWS CLI configured (`aws configure` or environment credentials)
4. GitHub CLI (`gh`) for bootstrap script
5. Docker Hub credentials for private image pulls

## Bootstrap (One-Time Setup)

The bootstrap script creates the OIDC provider, deploy role, policies, and Terraform state backend:

```powershell
./migrate/scripts/Initialize-Migration.ps1 -Environment dev -AwsRegion us-east-2
```

This creates:
- GitHub Actions OIDC provider in IAM
- Deploy IAM role with OIDC trust for your repo
- ReadOnlyAccess + SecurityAudit + AWSBillingReadOnlyAccess attached
- Deploy write policy for infrastructure management
- S3 bucket + DynamoDB table for Terraform state
- GitHub secrets/variables configured

## Deployment

```bash
cd migrate

# 1. Initialize with S3 backend
terraform init \
  -backend-config="bucket=cna-dev-tfstate-ACCOUNT_ID" \
  -backend-config="key=migrate.tfstate" \
  -backend-config="region=us-east-2" \
  -backend-config="dynamodb_table=cna-dev-tfstate-lock"

# 2. Set variables
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars

# 3. Plan and apply
terraform plan -out=tfplan
terraform apply tfplan
```

## CI/CD (GitHub Actions)

```yaml
permissions:
  id-token: write
  contents: read

jobs:
  deploy:
    runs-on: ubuntu-latest
    environment: dev
    steps:
      - uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: ${{ secrets.AWS_DEPLOY_ROLE_ARN }}
          aws-region: ${{ secrets.AWS_REGION }}
      - run: terraform apply -auto-approve
```

## File Structure

```
migrate/
├── providers.tf              Terraform + AWS/GitHub providers, S3 backend
├── variables.tf              All input variables
├── locals.tf                 Naming and tags
├── vpc.tf                    VPC, subnets, NAT, IGW, route tables
├── security_groups.tf        ALB, ECS, RDS security groups
├── alb.tf                    Application Load Balancer + target groups
├── ecs.tf                    ECS cluster + 3 Fargate services
├── rds.tf                    RDS PostgreSQL
├── s3.tf                     S3 buckets + lifecycle policies
├── secrets.tf                Secrets Manager secrets
├── cloudfront.tf             CloudFront distribution + WAF v2
├── iam.tf                    IAM roles (task, execution, deploy OIDC)
├── outputs.tf                Deployment outputs
├── terraform.tfvars.example  Sample variable values
├── README.md                 This file
└── scripts/
    └── Initialize-Migration.ps1   Bootstrap script
```

## Post-Deployment

1. Note the `cloudfront_domain_name` output — this is your public URL
2. Update Entra ID app registration redirect URI: `https://<cloudfront-domain>/api/auth/callback/microsoft-entra-id`
3. Run database migrations via ECS task
4. Navigate to `https://<cloudfront-domain>` and sign in
