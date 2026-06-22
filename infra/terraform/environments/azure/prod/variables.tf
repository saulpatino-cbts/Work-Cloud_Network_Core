variable "api_image" {
  description = "Container image for CNA API (docker.io/example-namespace/cna-api:<tag>)"
  type        = string
  default     = "docker.io/example-namespace/cna-api:latest"
}

variable "worker_image" {
  description = "Container image for CNA worker (docker.io/example-namespace/cna-worker:<tag>)"
  type        = string
  default     = "docker.io/example-namespace/cna-worker:latest"
}

variable "web_image" {
  description = "Container image for CNA web (docker.io/example-namespace/cna-web:<tag>)"
  type        = string
  default     = "docker.io/example-namespace/cna-web:latest"
}

variable "tenant_id" {
  description = "Azure tenant ID"
  type        = string
  default     = "00000000-0000-0000-0000-000000000000"
}

variable "location" {
  description = "Azure region for CNA Platform deployment"
  type        = string
  default     = "southcentralus"
}

variable "region_short" {
  description = "Short region code used in resource names (e.g. scus, eus2, wus2)"
  type        = string
  default     = "scus"
}

variable "environment" {
  description = "Deployment environment"
  type        = string
  default     = "prod"
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

# ─── Container Registry ───────────────────────────────────────────────────────
variable "container_registry_username" {
  description = "Username for private container registry image pulls."
  type        = string
  default     = ""
}

variable "container_registry_password" {
  description = "Token or password for private container registry image pulls. Set from GitHub Secret DOCKERHUB_TOKEN for Docker Hub."
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
  description = "Canonical URL of the cna-web deployment in prod (used by NextAuth for callbacks)"
  type        = string
  default     = "https://cna.example.com"
}

variable "web_ingress_ip_security_restrictions" {
  description = "Optional web ingress IP restrictions for direct-origin hardening."
  type = list(object({
    name             = string
    action           = string
    ip_address_range = string
    description      = optional(string)
  }))
  default = []
}

variable "credential_encryption_key" {
  description = "Base64-encoded 32-byte AES-256 key for encrypting SP client secrets at rest. Generate with: openssl rand -base64 32"
  type        = string
  sensitive   = true
}

# ─── AI Engine + MCP configuration ────────────────────────────────────────────
variable "ai_engine_default" {
  description = "Default global GenAI engine when no database setting exists."
  type        = string
  default     = "foundry-claude"

  validation {
    condition     = contains(["azure-openai", "foundry-claude"], var.ai_engine_default)
    error_message = "ai_engine_default must be azure-openai or foundry-claude."
  }
}

variable "foundry_claude_endpoint" {
  description = "Foundry Claude Messages API endpoint for the web app."
  type        = string
  default     = ""
}

variable "foundry_claude_model" {
  description = "Foundry Claude model identifier."
  type        = string
  default     = "claude-sonnet-4-6"
}

variable "azure_mcp_endpoint" {
  description = "Azure MCP server endpoint surfaced in cna-web."
  type        = string
  default     = "https://mcp.azure.com"
}

variable "azure_mcp_transport" {
  description = "Azure MCP server transport."
  type        = string
  default     = "streamable-http"
}

variable "aws_mcp_endpoint" {
  description = "AWS MCP server endpoint surfaced in cna-web."
  type        = string
  default     = "https://aws-mcp.us-east-1.api.aws/mcp"
}

variable "aws_mcp_transport" {
  description = "AWS MCP server transport."
  type        = string
  default     = "streamable-http"
}

variable "drawio_mcp_url" {
  description = "draw.io MCP endpoint surfaced in cna-web."
  type        = string
  default     = ""
}
