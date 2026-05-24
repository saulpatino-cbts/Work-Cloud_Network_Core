resource "azurerm_application_insights" "this" {
  name                = local.app_insights_name
  location            = var.location
  resource_group_name = var.resource_group_name
  application_type    = var.application_type
  tags                = var.tags
}

resource "azurerm_cognitive_account" "this" {
  #checkov:skip=CKV2_AZURE_22:Customer-managed key support for Azure OpenAI is deferred until key lifecycle and regional support are validated.
  #checkov:skip=CKV_AZURE_247:DLP requires a validated outbound FQDN allowlist; outbound network access is restricted while the allowlist is finalized.
  name                  = local.cognitive_account_name
  location              = local.openai_location
  resource_group_name   = var.resource_group_name
  kind                  = "OpenAI"
  sku_name              = "S0"
  custom_subdomain_name = local.cognitive_account_name
  local_auth_enabled    = false

  public_network_access_enabled      = false
  outbound_network_access_restricted = true

  identity {
    type = "SystemAssigned"
  }

  network_acls {
    default_action = "Deny"
  }

  tags = var.tags
}

resource "azurerm_cognitive_deployment" "model" {
  name                 = var.openai_model_name
  cognitive_account_id = azurerm_cognitive_account.this.id

  model {
    format  = "OpenAI"
    name    = var.openai_model_name
    version = var.openai_model_version
  }

  sku {
    name     = "GlobalStandard"
    capacity = var.openai_deployment_capacity
  }
}
