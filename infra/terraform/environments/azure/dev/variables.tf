variable "api_image" {
  description = "Container image for CNA API (ghcr.io/saulpatinojr/cna-api:<tag>)"
  type        = string
  default     = "ghcr.io/saulpatinojr/cna-api:latest"
}

variable "worker_image" {
  description = "Container image for CNA worker (ghcr.io/saulpatinojr/cna-worker:<tag>)"
  type        = string
  default     = "ghcr.io/saulpatinojr/cna-worker:latest"
}

variable "web_image" {
  description = "Container image for CNA web (ghcr.io/saulpatinojr/cna-web:<tag>)"
  type        = string
  default     = "ghcr.io/saulpatinojr/cna-web:latest"
}

variable "tenant_id" {
  description = "Azure tenant ID"
  type        = string
  default     = "00000000-0000-0000-0000-000000000000"
}

variable "location" {
  description = "Azure region for CNA Platform deployment"
  type        = string
  default     = "eastus"
}

variable "environment" {
  description = "Deployment environment"
  type        = string
  default     = "dev"
}

variable "project_name" {
  description = "Project name prefix"
  type        = string
  default     = "cna"
}

# ─── PostgreSQL ────────────────────────────────────────────────────────────────
variable "postgres_admin_username" {
  description = "PostgreSQL administrator username"
  type        = string
  default     = "cnaadmin"
}

variable "postgres_admin_password" {
  description = "PostgreSQL administrator password — set from GitHub Secret CNA_POSTGRES_ADMIN_PASSWORD"
  type        = string
  sensitive   = true
}

# ─── Entra ID (Azure AD) ───────────────────────────────────────────────────────
variable "entra_client_id" {
  description = "Entra ID (Azure AD) application client ID for NextAuth Entra provider"
  type        = string
}

variable "entra_client_secret" {
  description = "Entra ID OAuth2 client secret — set from GitHub Secret CNA_ENTRA_CLIENT_SECRET"
  type        = string
  sensitive   = true
}

# ─── GHCR ─────────────────────────────────────────────────────────────────────
variable "ghcr_username" {
  description = "GitHub username for GHCR image pulls (matches the package owner)"
  type        = string
  default     = "saulpatinojr"
}

variable "ghcr_pat" {
  description = "GitHub PAT with read:packages scope — set from GitHub Secret GHCR_PAT"
  type        = string
  sensitive   = true
}

# ─── NextAuth ─────────────────────────────────────────────────────────────────
variable "nextauth_secret" {
  description = "NextAuth.js JWT signing secret — generate with: openssl rand -base64 32"
  type        = string
  sensitive   = true
}

variable "nextauth_url" {
  description = "Canonical URL of the cna-web deployment (used by NextAuth for callbacks)"
  type        = string
  default     = "https://cna.example.com"
}
