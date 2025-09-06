# Storage Module Outputs

output "s3_bucket_names" {
  description = "Names of the S3 buckets created"
  value = var.create_s3_examples ? [
    aws_s3_bucket.static_website[0].bucket,
    aws_s3_bucket.data_store[0].bucket,
    aws_s3_bucket.logs[0].bucket
  ] : []
}

output "s3_bucket_arns" {
  description = "ARNs of the S3 buckets created"
  value = var.create_s3_examples ? [
    aws_s3_bucket.static_website[0].arn,
    aws_s3_bucket.data_store[0].arn,
    aws_s3_bucket.logs[0].arn
  ] : []
}

output "s3_website_endpoint" {
  description = "Website endpoint for the static website bucket"
  value       = var.create_s3_examples ? aws_s3_bucket_website_configuration.static_website[0].website_endpoint : null
}

output "efs_file_system_ids" {
  description = "IDs of the EFS file systems"
  value       = var.create_efs_examples ? [aws_efs_file_system.main[0].id] : []
}

output "efs_file_system_arn" {
  description = "ARN of the EFS file system"
  value       = var.create_efs_examples ? aws_efs_file_system.main[0].arn : null
}

output "efs_mount_target_ids" {
  description = "IDs of the EFS mount targets"
  value       = var.create_efs_examples ? aws_efs_mount_target.main[*].id : []
}

output "efs_dns_names" {
  description = "DNS name of the EFS file system"
  value       = var.create_efs_examples ? "${aws_efs_file_system.main[0].id}.efs.${data.aws_region.current.name}.amazonaws.com" : null
}

output "efs_access_point_id" {
  description = "ID of the EFS access point"
  value       = var.create_efs_examples ? aws_efs_access_point.main[0].id : null
}

output "efs_security_group_id" {
  description = "ID of the EFS security group"
  value       = var.create_efs_examples ? aws_security_group.efs[0].id : null
}

# Current region for EFS DNS name
data "aws_region" "current" {}
