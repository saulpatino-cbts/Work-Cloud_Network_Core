locals {
  cdn_profile_name = "cdn-${var.name_prefix}-platform"
  cdn_endpoint_name = substr(replace(lower("cdn-${var.name_prefix}-site"), "-", ""), 0, 50)
}
