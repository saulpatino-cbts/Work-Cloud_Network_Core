locals {
  container_apps_env_name = "cae-${var.name_prefix}-platform"
  api_app_name            = "ca-${var.name_prefix}-api"
  worker_app_name         = "ca-${var.name_prefix}-worker"
}
