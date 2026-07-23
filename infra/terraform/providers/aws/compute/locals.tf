locals {
  # Mirrors Azure compute's per-service naming (api_app_name/worker_app_name/
  # web_app_name) -- actual ECS service/task-family names once Fargate is confirmed.
  api_service_name    = "${var.name_prefix}-api"
  worker_service_name = "${var.name_prefix}-worker"
  web_service_name    = "${var.name_prefix}-web"
}
