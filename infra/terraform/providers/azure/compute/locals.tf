locals {
  container_apps_env_name = "cae-${var.name_prefix}-platform"
  api_app_name            = "ca-${var.name_prefix}-api"
  worker_app_name         = "ca-${var.name_prefix}-worker"

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
}
