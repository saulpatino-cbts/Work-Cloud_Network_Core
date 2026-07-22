locals {
  name_prefix = "${var.project_name}-${var.environment}"

  tags = {
    Environment = var.environment
    Project     = var.project_name
    ManagedBy   = "terraform"
  }

  # Determine the app URL: custom domain or CloudFront default
  app_url = var.nextauth_url != "" ? var.nextauth_url : "https://${aws_cloudfront_distribution.main.domain_name}"
}
