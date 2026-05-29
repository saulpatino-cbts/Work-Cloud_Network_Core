# Azure AI Module

Provision Microsoft Foundry and observability resources for the CNA Platform.

This module owns:
- Application Insights in the workload resource group.
- A regional Microsoft Foundry `AIServices` account.
- A Foundry project under that account.

It no longer provisions an Azure OpenAI `OpenAI` cognitive account or model deployment.
