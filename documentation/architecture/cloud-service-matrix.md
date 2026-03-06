# Cloud Service Matrix

> Version: 1.0.0 | Status: Draft | Date: 2026-03-06

This document compares AWS and Azure service selections for the CNA Platform.

---

## Service Comparison

| Capability | AWS Target | Azure Target | Why This Pairing |
|---|---|---|---|
| Upload/API ingress | API Gateway or ALB | API Management or Container Apps ingress | Managed edge with application-controlled processing |
| Object storage | S3 | Blob Storage | Durable artifact landing and delivery storage |
| Worker runtime | ECS Fargate | Container Apps | Managed container execution with low operational overhead |
| Async messaging | SQS | Service Bus | Reliable decoupled processing |
| Metadata persistence | RDS PostgreSQL | Azure Database for PostgreSQL | Structured assessment/job state |
| AI provider | Bedrock | Azure OpenAI | Native cloud AI integration |
| Static website | CloudFront + S3 | Static Web Apps or Blob + CDN | Low-friction presentation layer |
| Secrets | Secrets Manager / SSM | Key Vault | Native secure secret retrieval |
| Identity | IAM roles | Managed Identity / Entra ID | Least-privilege service auth |
| Monitoring | CloudWatch | Azure Monitor | Native logs and metrics |

---

## Container-First Principle

The CNA Platform should be implemented as a container-first application stack.

This keeps the application runtime portable while still allowing cloud-native identity, storage, messaging, and AI integrations.

---

## Kubernetes Position

Kubernetes is not the recommended first deployment target.

The first hosted version should prioritize lower operational overhead using managed container services. Kubernetes can be adopted later if workload complexity, scale, or customization justifies it.
