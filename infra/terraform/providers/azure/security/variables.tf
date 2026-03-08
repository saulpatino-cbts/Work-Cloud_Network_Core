variable "resource_group_name" {
  description = "Resource group name containing the Key Vault"
  type        = string
}

variable "location" {
  description = "Azure location"
  type        = string
}

variable "name_prefix" {
  description = "Normalized name prefix for security resources"
  type        = string
}

variable "key_vault_id" {
  description = "Key Vault resource ID"
  type        = string
}

variable "key_vault_name" {
  description = "Key Vault name"
  type        = string
}

variable "managed_identity_principal_id" {
  description = "Managed identity principal ID used for Key Vault access"
  type        = string
}

variable "managed_identity_id" {
  description = "Managed identity resource ID"
  type        = string
}

variable "managed_identity_client_id" {
  description = "Managed identity client ID"
  type        = string
}

variable "api_container_app_id" {
  description = "API Container App resource ID"
  type        = string
}

variable "api_container_app_fqdn" {
  description = "API Container App FQDN (internal, kept for reference)"
  type        = string
}

variable "web_container_app_fqdn" {
  description = "Web (Next.js) Container App FQDN — used as Azure Front Door origin host"
  type        = string
}

variable "web_container_app_id" {
  description = "Web (Next.js) Container App resource ID"
  type        = string
}

variable "worker_container_app_id" {
  description = "Worker Container App resource ID"
  type        = string
}

variable "azure_openai_account_id" {
  description = "Azure OpenAI cognitive account resource ID used for private endpoint integration"
  type        = string
}

variable "azure_openai_endpoint" {
  description = "Azure OpenAI endpoint"
  type        = string
}

variable "application_insights_connection_string" {
  description = "Application Insights connection string"
  type        = string
}

variable "allowed_api_cidrs" {
  description = "CIDR ranges allowed to reach the API front door"
  type        = list(string)
  default     = ["0.0.0.0/0"]
}

variable "frontdoor_custom_domain_host_name" {
  description = "Optional custom domain hostname for Azure Front Door"
  type        = string
  default     = ""
}

variable "frontdoor_custom_domain_dns_zone_id" {
  description = "Optional Azure DNS zone resource ID for Front Door custom domain integration"
  type        = string
  default     = null
}

variable "frontdoor_certificate_type" {
  description = "Certificate type for Front Door custom domain TLS"
  type        = string
  default     = "ManagedCertificate"
}

variable "frontdoor_minimum_tls_version" {
  description = "Minimum TLS version for Front Door custom domain TLS"
  type        = string
  default     = "TLS12"
}

variable "frontdoor_secret_versionless_id" {
  description = "Optional Key Vault certificate secret versionless ID for customer-managed Front Door TLS"
  type        = string
  default     = null
}

variable "virtual_network_id" {
  description = "Virtual network ID used for private DNS links"
  type        = string
}

variable "private_endpoint_subnet_id" {
  description = "Subnet ID used for private endpoints"
  type        = string
}

variable "storage_account_id" {
  description = "Storage account resource ID for private endpoint"
  type        = string
}

variable "storage_account_name" {
  description = "Storage account name for private DNS wiring"
  type        = string
}
