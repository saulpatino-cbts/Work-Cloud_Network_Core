resource "azurerm_application_insights" "this" {
  name                = local.app_insights_name
  location            = var.location
  resource_group_name = var.resource_group_name
  application_type    = var.application_type
  tags                = var.tags
}

resource "azurerm_cognitive_account" "this" {
  name                  = local.cognitive_account_name
  location              = local.openai_location
  resource_group_name   = var.resource_group_name
  kind                  = "OpenAI"
  sku_name              = "S0"
  custom_subdomain_name = local.cognitive_account_name
  tags                  = var.tags
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
