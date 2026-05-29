import {
  to = module.ai.azurerm_resource_group.foundry
  id = "/subscriptions/${data.azurerm_client_config.current.subscription_id}/resourceGroups/rg-cna-ai-dev-eus2"
}

import {
  to = module.ai.azurerm_cognitive_account.foundry
  id = "/subscriptions/${data.azurerm_client_config.current.subscription_id}/resourceGroups/rg-cna-ai-dev-eus2/providers/Microsoft.CognitiveServices/accounts/fdry-cna-dev-eus2"
}

import {
  to = module.ai.azapi_resource.foundry_project
  id = "/subscriptions/${data.azurerm_client_config.current.subscription_id}/resourceGroups/rg-cna-ai-dev-eus2/providers/Microsoft.CognitiveServices/accounts/fdry-cna-dev-eus2/projects/proj-cna-dev-eus2"
}
