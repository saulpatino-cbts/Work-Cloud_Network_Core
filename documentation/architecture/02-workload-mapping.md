# 02 — Workload Mapping

> Version: 1.0.0 | Status: Draft | Date: 2026-03-06

This document maps CNA Platform workload capabilities to AWS and Azure service options.

---

## Objective

`02-workload-mapping` defines the concrete cloud service choices that implement the hosted CNA Platform in Azure and AWS.

The workload contract remains shared across clouds. The service realization is cloud-specific.

---

## Decision Model

Each workload is documented with:
- primary AWS target
- primary Azure target
- acceptable alternatives
- rationale for initial platform implementation

---

## Workload Mapping

| Workload | AWS Primary | Azure Primary | Alternatives | Notes |
|---|---|---|---|---|
| Ingress Service | API Gateway + Lambda or ALB + ECS/Fargate | API Management + Container Apps | App Runner, App Service | Prefer container-friendly ingress if shared app runtime is needed |
| Raw Artifact Storage | S3 | Blob Storage | EFS / Azure Files for niche cases | Object storage is the system of record for source artifacts |
| Processing Compute | ECS Fargate | Container Apps | EKS, AKS | Start with managed containers before Kubernetes |
| Orchestration Layer | SQS + EventBridge | Service Bus + Container Apps Jobs | Step Functions, Logic Apps | Keep orchestration async and replayable |
| Metadata Store | RDS PostgreSQL | Azure Database for PostgreSQL | DynamoDB, Cosmos DB | Prefer relational metadata first for traceability |
| AI Integration Layer | Bedrock | Azure OpenAI | Self-hosted model gateway | Abstract provider choice behind app layer |
| Visualization and Delivery Site | S3 Static Website + CloudFront | Static Web Apps or Blob Static Website + CDN | Amplify, Front Door | Static delivery surface should stay simple |
| Secrets and Identity Layer | IAM + Secrets Manager / SSM | Managed Identity + Key Vault | Vault | Prefer native cloud identity first |
| Observability Layer | CloudWatch + X-Ray | Azure Monitor + Application Insights | Datadog, OpenTelemetry collector | Use native services before external platforms |

---

## Initial Deployment Recommendation

### AWS-first minimal slice
- API Gateway or ALB-backed upload/API ingress
- S3 for raw and generated artifacts
- ECS Fargate for processing workers
- SQS for async jobs
- PostgreSQL for metadata
- Bedrock integration for AI-assisted processing
- S3 + CloudFront for delivery surface

### Azure-first minimal slice
- Container Apps ingress or API Management front door
- Blob Storage for raw and generated artifacts
- Container Apps for processing workers
- Service Bus for async jobs
- PostgreSQL flexible server for metadata
- Azure OpenAI for AI-assisted processing
- Static Web Apps or Blob static site for delivery surface

---

## Platform Principle

The CNA Platform should be deployable to either cloud without changing the workload model.

The service mapping may differ, but the platform responsibilities must remain the same.
