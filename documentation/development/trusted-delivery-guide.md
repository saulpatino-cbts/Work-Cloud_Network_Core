# Trusted Delivery Guide

> Version: 1.0.0 | Status: Draft | Date: 2026-03-06

This guide describes the trusted delivery controls added for Azure Terraform deployment.

---

## Added Controls

The delivery workflow now includes:
- Azure login through GitHub OIDC
- explicit AzureRM backend configuration inputs
- tfsec Terraform security scanning
- scheduled drift detection

---

## Required Setup

Configure these GitHub secrets:
- `AZURE_CLIENT_ID`
- `AZURE_TENANT_ID`
- `AZURE_SUBSCRIPTION_ID`

Configure these GitHub repository or environment variables:
- `TFSTATE_RESOURCE_GROUP`
- `TFSTATE_STORAGE_ACCOUNT`
- `TFSTATE_CONTAINER`

---

## Design Intent

These controls move the platform closer to trusted, reviewable, and governed cloud delivery.
