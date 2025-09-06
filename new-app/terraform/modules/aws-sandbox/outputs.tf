# AWS Terraform Sandbox Module Outputs

# VPC outputs
output "vpc_id" {
  description = "The ID of the VPC"
  value       = module.vpc.vpc_id
}

output "vpc_cidr_block" {
  description = "The CIDR block of the VPC"
  value       = module.vpc.vpc_cidr_block
}

output "public_subnet_ids" {
  description = "List of IDs of public subnets"
  value       = module.vpc.public_subnet_ids
}

output "private_subnet_ids" {
  description = "List of IDs of private subnets"
  value       = module.vpc.private_subnet_ids
}

output "database_subnet_ids" {
  description = "List of IDs of database subnets"
  value       = module.vpc.database_subnet_ids
}

# Compute outputs
output "bastion_public_ip" {
  description = "Public IP of the bastion host"
  value       = var.enable_compute_examples && var.create_bastion ? module.compute[0].bastion_public_ip : null
}

output "ec2_instance_ids" {
  description = "IDs of the EC2 instances"
  value       = var.enable_compute_examples && var.create_ec2_examples ? module.compute[0].ec2_instance_ids : null
}

output "asg_names" {
  description = "Names of the Auto Scaling Groups"
  value       = var.enable_compute_examples && var.create_asg_examples ? module.compute[0].asg_names : null
}

# Database outputs
output "rds_instance_endpoints" {
  description = "Endpoints of the RDS instances"
  value       = var.enable_database_examples && var.create_rds_examples ? module.database[0].rds_instance_endpoints : null
}

output "dynamodb_table_names" {
  description = "Names of the DynamoDB tables"
  value       = var.enable_database_examples && var.create_dynamodb_examples ? module.database[0].dynamodb_table_names : null
}

# Storage outputs
output "s3_bucket_names" {
  description = "Names of the S3 buckets"
  value       = var.enable_storage_examples && var.create_s3_examples ? module.storage[0].s3_bucket_names : null
}

output "efs_file_system_ids" {
  description = "IDs of the EFS file systems"
  value       = var.enable_storage_examples && var.create_efs_examples ? module.storage[0].efs_file_system_ids : null
}

# Serverless outputs
output "lambda_function_names" {
  description = "Names of the Lambda functions"
  value       = var.enable_serverless_examples && var.create_lambda_examples ? module.serverless[0].lambda_function_names : null
}

output "api_gateway_endpoints" {
  description = "Endpoints of the API Gateways"
  value       = var.enable_serverless_examples && var.create_apigateway_examples ? module.serverless[0].api_gateway_endpoints : null
}

output "stepfunctions_state_machine_arns" {
  description = "ARNs of the Step Functions state machines"
  value       = var.enable_serverless_examples && var.create_stepfunctions_examples ? module.serverless[0].stepfunctions_state_machine_arns : null
}

# Security outputs
output "iam_role_arns" {
  description = "ARNs of the IAM roles"
  value       = var.enable_security_examples && var.create_iam_examples ? module.security[0].iam_role_arns : null
}

output "kms_key_arns" {
  description = "ARNs of the KMS keys"
  value       = var.enable_security_examples && var.create_kms_examples ? module.security[0].kms_key_arns : null
}

# Networking outputs
output "route53_zone_names" {
  description = "Names of the Route 53 zones"
  value       = var.enable_networking_examples && var.create_route53_examples ? module.networking[0].route53_zone_names : null
}

output "cloudfront_distribution_domains" {
  description = "Domain names of the CloudFront distributions"
  value       = var.enable_networking_examples && var.create_cloudfront_examples ? module.networking[0].cloudfront_distribution_domains : null
}

output "load_balancer_dns_names" {
  description = "DNS names of the load balancers"
  value       = var.enable_networking_examples && var.create_elb_examples ? module.networking[0].load_balancer_dns_names : null
}

# Container outputs
output "ecr_repository_urls" {
  description = "URLs of the ECR repositories"
  value       = var.enable_container_examples && var.create_ecr_examples ? module.containers[0].ecr_repository_urls : null
}

output "eks_cluster_endpoints" {
  description = "Endpoints of the EKS clusters"
  value       = var.enable_container_examples && var.create_eks_examples ? module.containers[0].eks_cluster_endpoints : null
}

output "ecs_cluster_names" {
  description = "Names of the ECS clusters"
  value       = var.enable_container_examples && var.create_ecs_examples ? module.containers[0].ecs_cluster_names : null
}

# Monitoring outputs
output "cloudwatch_dashboard_names" {
  description = "Names of the CloudWatch dashboards"
  value       = var.enable_monitoring_examples && var.create_cloudwatch_examples ? module.monitoring[0].cloudwatch_dashboard_names : null
}

# AI/ML outputs
output "sagemaker_notebook_urls" {
  description = "URLs of the SageMaker notebooks"
  value       = var.enable_aiml_examples && var.create_sagemaker_examples ? module.ai_ml[0].sagemaker_notebook_urls : null
}

# DevOps outputs
output "codepipeline_names" {
  description = "Names of the CodePipelines"
  value       = var.enable_devops_examples && var.create_codepipeline_examples ? module.devops[0].codepipeline_names : null
}

# Comprehensive outputs in JSON format
output "sandbox_configuration" {
  description = "Complete sandbox configuration in JSON format"
  value = jsonencode({
    metadata = {
      project_name = var.project_name
      environment  = var.environment
      region       = var.region
      created_by   = var.created_by
      ttl_hours    = var.sandbox_ttl_hours
    }
    vpc = {
      id             = module.vpc.vpc_id
      cidr_block     = module.vpc.vpc_cidr_block
      public_subnets = module.vpc.public_subnet_ids
      private_subnets = module.vpc.private_subnet_ids
      database_subnets = module.vpc.database_subnet_ids
    }
    compute = var.enable_compute_examples ? {
      bastion_ip     = var.create_bastion ? module.compute[0].bastion_public_ip : null
      ec2_instances  = var.create_ec2_examples ? module.compute[0].ec2_instance_ids : null
      asg_names      = var.create_asg_examples ? module.compute[0].asg_names : null
    } : null
    database = var.enable_database_examples ? {
      rds_endpoints  = var.create_rds_examples ? module.database[0].rds_instance_endpoints : null
      dynamodb_tables = var.create_dynamodb_examples ? module.database[0].dynamodb_table_names : null
    } : null
    storage = var.enable_storage_examples ? {
      s3_buckets     = var.create_s3_examples ? module.storage[0].s3_bucket_names : null
      efs_systems    = var.create_efs_examples ? module.storage[0].efs_file_system_ids : null
    } : null
    serverless = var.enable_serverless_examples ? {
      lambda_functions = var.create_lambda_examples ? module.serverless[0].lambda_function_names : null
      api_gateways    = var.create_apigateway_examples ? module.serverless[0].api_gateway_endpoints : null
      state_machines  = var.create_stepfunctions_examples ? module.serverless[0].stepfunctions_state_machine_arns : null
    } : null
    security = var.enable_security_examples ? {
      iam_roles       = var.create_iam_examples ? module.security[0].iam_role_arns : null
      kms_keys        = var.create_kms_examples ? module.security[0].kms_key_arns : null
    } : null
    networking = var.enable_networking_examples ? {
      route53_zones   = var.create_route53_examples ? module.networking[0].route53_zone_names : null
      cloudfront_distributions = var.create_cloudfront_examples ? module.networking[0].cloudfront_distribution_domains : null
      load_balancers  = var.create_elb_examples ? module.networking[0].load_balancer_dns_names : null
    } : null
    containers = var.enable_container_examples ? {
      ecr_repos       = var.create_ecr_examples ? module.containers[0].ecr_repository_urls : null
      eks_clusters    = var.create_eks_examples ? module.containers[0].eks_cluster_endpoints : null
      ecs_clusters    = var.create_ecs_examples ? module.containers[0].ecs_cluster_names : null
    } : null
    monitoring = var.enable_monitoring_examples ? {
      dashboards      = var.create_cloudwatch_examples ? module.monitoring[0].cloudwatch_dashboard_names : null
    } : null
    ai_ml = var.enable_aiml_examples ? {
      sagemaker_notebooks = var.create_sagemaker_examples ? module.ai_ml[0].sagemaker_notebook_urls : null
    } : null
    devops = var.enable_devops_examples ? {
      pipelines       = var.create_codepipeline_examples ? module.devops[0].codepipeline_names : null
    } : null
  })
}
