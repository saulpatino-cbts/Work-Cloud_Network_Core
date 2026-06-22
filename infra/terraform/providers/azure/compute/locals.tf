locals {
  container_apps_env_name = "${var.name_prefix}-cae"
  container_apps_infra_resource_group_name = coalesce(
    var.container_app_environment_infrastructure_resource_group_name,
    "rg-${var.name_prefix}-cae-managed"
  )
  api_app_name    = "${var.name_prefix}-ca-api"
  worker_app_name = "${var.name_prefix}-ca-worker"
  web_app_name    = "${var.name_prefix}-ca-web"

  # Private non-ACR registries such as Docker Hub use username + token auth.
  # If credentials are omitted, the registry block falls back to managed identity for ACR.
  use_registry_credentials = nonsensitive(var.container_registry_username != "" && var.container_registry_password != "")

  api_plain_env_vars = [
    for name, value in var.api_env_vars : {
      name  = name
      value = value
    }
  ]

  worker_plain_env_vars = [
    for name, value in var.worker_env_vars : {
      name  = name
      value = value
    }
  ]

  web_plain_env_vars = [
    for name, value in var.web_env_vars : {
      name  = name
      value = value
    }
  ]

  api_secret_env_vars = [
    for name, secret_name in var.api_secret_env_vars : {
      name        = name
      secret_name = secret_name
    }
  ]

  worker_secret_env_vars = [
    for name, secret_name in var.worker_secret_env_vars : {
      name        = name
      secret_name = secret_name
    }
  ]

  web_secret_env_vars = [
    for name, secret_name in var.web_secret_env_vars : {
      name        = name
      secret_name = secret_name
    }
  ]

  # Force a new Container App revision whenever a secret VALUE or the image
  # changes. Azure does NOT roll a revision on a secret-value-only change, so an
  # updated secret (e.g. a corrected DATABASE_URL) would otherwise leave running
  # replicas pinned to the stale value and crash-loop. Binding revision_suffix to
  # a hash of (image + secret values) makes Terraform create a fresh revision that
  # re-injects the current secrets — no manual restart, no CI compensation needed.
  # nonsensitive() is safe here: a SHA-1 digest does not reveal the secret values.
  secrets_hash = nonsensitive(sha1(join("|", [
    for k in sort(keys(var.container_app_secrets)) : "${k}=${var.container_app_secrets[k]}"
  ])))

  api_revision_suffix    = "r${substr(sha1("${var.api_image}|${local.secrets_hash}"), 0, 10)}"
  worker_revision_suffix = "r${substr(sha1("${var.worker_image}|${local.secrets_hash}"), 0, 10)}"
  web_revision_suffix    = "r${substr(sha1("${var.web_image}|${local.secrets_hash}"), 0, 10)}"
}
