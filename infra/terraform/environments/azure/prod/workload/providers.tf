terraform {
  required_version = ">= 1.9.0"

  backend "azurerm" {}

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }
    azapi = {
      source  = "azure/azapi"
      version = "~> 2.0"
    }
    github = {
      source  = "integrations/github"
      version = "~> 6.0"
    }
  }
}

provider "azurerm" {
  features {
    resource_group {
      # Confirmed environment teardown must remove Azure-created child resources
      # that are not addressable in Terraform state, such as Smart Detection.
      prevent_deletion_if_contains_resources = false
    }
  }
  use_oidc = true
}

data "azurerm_client_config" "current" {}

provider "azapi" {
  use_oidc = true
}

provider "github" {
  owner = var.github_owner
  token = var.github_token
}
