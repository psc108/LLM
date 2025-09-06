# Database Module Outputs

output "rds_instance_endpoints" {
  description = "Endpoints of the RDS instances"
  value = var.create_rds_examples && length(var.database_subnet_ids) > 1 ? {
    mysql    = try(aws_db_instance.mysql[0].endpoint, null)
    postgres = try(aws_db_instance.postgres[0].endpoint, null)
  } : null
}

output "rds_instance_ids" {
  description = "IDs of the RDS instances"
  value = var.create_rds_examples && length(var.database_subnet_ids) > 1 ? {
    mysql    = try(aws_db_instance.mysql[0].id, null)
    postgres = try(aws_db_instance.postgres[0].id, null)
  } : null
}

output "rds_usernames" {
  description = "Master usernames for RDS instances"
  value = var.create_rds_examples && length(var.database_subnet_ids) > 1 ? {
    mysql    = try(aws_db_instance.mysql[0].username, null)
    postgres = try(aws_db_instance.postgres[0].username, null)
  } : null
}

output "rds_passwords" {
  description = "Master passwords for RDS instances"
  value = var.create_rds_examples && length(var.database_subnet_ids) > 1 ? {
    mysql    = try(random_password.mysql[0].result, null)
    postgres = try(random_password.postgres[0].result, null)
  } : null
  sensitive = true
}

output "dynamodb_table_names" {
  description = "Names of the DynamoDB tables"
  value = var.create_dynamodb_examples ? {
    basic    = try(aws_dynamodb_table.basic[0].name, null)
    advanced = try(aws_dynamodb_table.advanced[0].name, null)
    ttl      = try(aws_dynamodb_table.ttl_example[0].name, null)
  } : null
}

output "dynamodb_table_arns" {
  description = "ARNs of the DynamoDB tables"
  value = var.create_dynamodb_examples ? {
    basic    = try(aws_dynamodb_table.basic[0].arn, null)
    advanced = try(aws_dynamodb_table.advanced[0].arn, null)
    ttl      = try(aws_dynamodb_table.ttl_example[0].arn, null)
  } : null
}

output "db_subnet_group_name" {
  description = "Name of the DB subnet group"
  value       = var.create_rds_examples && length(var.database_subnet_ids) > 1 ? try(aws_db_subnet_group.main[0].name, null) : null
}

output "db_security_group_id" {
  description = "ID of the DB security group"
  value       = aws_security_group.rds.id
}

output "kms_key_arn" {
  description = "ARN of the KMS key used for RDS encryption"
  value       = var.create_rds_examples ? try(aws_kms_key.rds[0].arn, null) : null
}

output "kms_key_id" {
  description = "ID of the KMS key used for RDS encryption"
  value       = var.create_rds_examples ? try(aws_kms_key.rds[0].key_id, null) : null
}
