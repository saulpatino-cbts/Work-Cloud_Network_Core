resource "azurerm_cognitive_account" "foundry" {
  name                          = var.foundry_account_name
  location                      = var.foundry_location
  resource_group_name           = var.resource_group_name
  kind                          = "AIServices"
  sku_name                      = "S0"
  custom_subdomain_name         = var.foundry_account_name
  project_management_enabled    = true
  local_auth_enabled            = false
  public_network_access_enabled = false

  identity {
    type = "SystemAssigned"
  }

  tags = merge(var.tags, local.foundry_tags)
}

# The project is a child resource of the Cognitive Services account. Terraform's
# implicit dependency via parent_id only waits for the account's create call to
# return, not for it to reach a terminal provisioning state — the same
# "RequestConflict: provisioning state is not terminal" race already handled
# for private endpoints in the security module (time_sleep.private_endpoint_settle).
resource "time_sleep" "foundry_account_settle" {
  create_duration = "30s"

  triggers = {
    foundry_account_id = azurerm_cognitive_account.foundry.id
  }
}

resource "azapi_resource" "foundry_project" {
  type      = "Microsoft.CognitiveServices/accounts/projects@2025-06-01"
  name      = var.foundry_project_name
  parent_id = azurerm_cognitive_account.foundry.id
  location  = var.foundry_location

  depends_on = [time_sleep.foundry_account_settle]

  body = {
    identity = {
      type = "SystemAssigned"
    }
    properties = {
      displayName = var.foundry_project_name
      description = "CNA ${var.environment} Foundry project hosting the Azure OpenAI deployment"
    }
  }

  tags = merge(var.tags, local.foundry_tags)
}
