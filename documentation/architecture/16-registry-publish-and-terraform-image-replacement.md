# 16 — Registry Publish and Terraform Image Replacement

> Version: 1.0.0 | Status: Draft | Date: 2026-03-06

This document defines the first transition from placeholder runtime images to CNA-owned application images in Terraform.

---

## Objective

`16-registry-publish-and-terraform-image-replacement` updates the Azure runtime so Container Apps can use CNA platform image references instead of sample images.

---

## Delivered Changes

| Component | Responsibility |
|---|---|
| `providers/azure/compute` | Parameterized runtime images for API and worker services |
| `environments/azure/dev` | Exposes image variables for development deployments |
| `environments/azure/prod` | Exposes image variables for production deployments |

---

## Image Defaults

Initial defaults:
- `ghcr.io/saulpatinojr/cna-api:latest`
- `ghcr.io/saulpatinojr/cna-worker:latest`

These are placeholders for the registry-backed CNA runtime image contract and should later be versioned by environment and release.

---

## Next Steps

A later workstream should add:
- GitHub Actions image build and publish workflow
- registry authentication strategy for Azure Container Apps
- environment-specific image tags
- deployment promotion between dev and prod
