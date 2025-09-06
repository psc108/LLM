# AWS Terraform Sandbox Module
# This module provides a comprehensive sandbox environment for AWS resources

# AWS Provider configuration
provider "aws" {
  region = var.region

  # Optional profile and assume role configuration
  profile = var.aws_profile != "" ? var.aws_profile : null
  dynamic "assume_role" {
    for_each = var.assume_role_arn != "" ? [1] : []
    content {
      role_arn = var.assume_role_arn
    }
  }

  # Optional default tags that apply to all resources
  default_tags {
    tags = merge(
      var.default_tags,
      {
        Environment = var.environment
        Project     = var.project_name
        Terraform   = "true"
        Sandbox     = "true"
      }
    )
  }
}

# Generate a random suffix for unique resource naming
resource "random_string" "suffix" {
  length  = 8
  special = false
  upper   = false
}

locals {
  # Common name prefix for resources
  name_prefix = "${var.project_name}-${var.environment}"

  # Common suffix for globally unique resources
  name_suffix = random_string.suffix.result

  # Full resource identifier
  resource_id = "${local.name_prefix}-${local.name_suffix}"

  # Common tags for all resources
  common_tags = {
    ManagedBy  = "terraform"
    CreatedBy  = var.created_by
    SandboxTTL = var.sandbox_ttl_hours
  }
}

# Include the core network infrastructure
module "vpc" {
  source = "modules/vpc"

  name_prefix              = local.name_prefix
  vpc_cidr                 = var.vpc_cidr
  azs                      = var.azs
  public_subnet_cidrs      = var.public_subnet_cidrs
  private_subnet_cidrs     = var.private_subnet_cidrs
  database_subnet_cidrs    = var.database_subnet_cidrs
  create_nat_gateway       = var.create_nat_gateway
  enable_vpn_gateway       = var.enable_vpn_gateway
  enable_vpc_flow_logs     = var.enable_vpc_flow_logs
  common_tags              = local.common_tags
}

# Include compute resources if enabled
module "compute" {
  count  = var.enable_compute_examples ? 1 : 0
  source = "modules/compute"

  name_prefix         = local.name_prefix
  vpc_id              = module.vpc.vpc_id
  public_subnet_ids   = module.vpc.public_subnet_ids
  private_subnet_ids  = module.vpc.private_subnet_ids
  create_bastion      = var.create_bastion
  create_ec2_examples = var.create_ec2_examples
  create_asg_examples = var.create_asg_examples
  create_ecs_examples = var.create_ecs_examples
  instance_type       = var.instance_type
  create_key_pair     = var.create_key_pair
  key_name            = var.key_name
  ssh_public_key      = var.ssh_public_key
  common_tags         = local.common_tags
}

# Include database resources if enabled
module "database" {
  count  = var.enable_database_examples ? 1 : 0
  source = "modules/database"

  name_prefix            = local.name_prefix
  vpc_id                 = module.vpc.vpc_id
  database_subnet_ids    = module.vpc.database_subnet_ids
  create_rds_examples    = var.create_rds_examples
  create_dynamodb_examples = var.create_dynamodb_examples
  rds_instance_class     = var.rds_instance_class
  common_tags            = local.common_tags
}

# Include storage resources if enabled
module "storage" {
  count  = var.enable_storage_examples ? 1 : 0
  source = "modules/storage"

  name_prefix          = local.name_prefix
  create_s3_examples   = var.create_s3_examples
  create_efs_examples  = var.create_efs_examples
  vpc_id               = module.vpc.vpc_id
  private_subnet_ids   = module.vpc.private_subnet_ids
  common_tags          = local.common_tags
}

# Include serverless resources if enabled
module "serverless" {
  count  = var.enable_serverless_examples ? 1 : 0
  source = "modules/serverless"

  name_prefix                = local.name_prefix
  create_lambda_examples     = var.create_lambda_examples
  create_apigateway_examples = var.create_apigateway_examples
  create_stepfunctions_examples = var.create_stepfunctions_examples
  vpc_id                     = module.vpc.vpc_id
  private_subnet_ids         = module.vpc.private_subnet_ids
  common_tags                = local.common_tags
}

# Include security resources if enabled
module "security" {
  count  = var.enable_security_examples ? 1 : 0
  source = "./modules/security"

  name_prefix               = local.name_prefix
  vpc_id                    = module.vpc.vpc_id
  create_iam_examples       = var.create_iam_examples
  create_kms_examples       = var.create_kms_examples
  create_waf_examples       = var.create_waf_examples
  create_securityhub_examples = var.create_securityhub_examples
  common_tags               = local.common_tags
}

# Include networking resources if enabled
module "networking" {
  count  = var.enable_networking_examples ? 1 : 0
  source = "./modules/networking"

  name_prefix                = local.name_prefix
  vpc_id                     = module.vpc.vpc_id
  create_route53_examples    = var.create_route53_examples
  create_cloudfront_examples = var.create_cloudfront_examples
  create_elb_examples        = var.create_elb_examples
  create_vpce_examples       = var.create_vpce_examples
  public_subnet_ids          = module.vpc.public_subnet_ids
  private_subnet_ids         = module.vpc.private_subnet_ids
  common_tags                = local.common_tags
}

# Include container resources if enabled
module "containers" {
  count  = var.enable_container_examples ? 1 : 0
  source = "./modules/containers"

  name_prefix             = local.name_prefix
  vpc_id                  = module.vpc.vpc_id
  create_ecr_examples     = var.create_ecr_examples
  create_eks_examples     = var.create_eks_examples
  create_ecs_examples     = var.create_ecs_examples
  private_subnet_ids      = module.vpc.private_subnet_ids
  common_tags             = local.common_tags
}

# Include monitoring resources if enabled
module "monitoring" {
  count  = var.enable_monitoring_examples ? 1 : 0
  source = "./modules/monitoring"

  name_prefix                = local.name_prefix
  vpc_id                     = module.vpc.vpc_id
  create_cloudwatch_examples = var.create_cloudwatch_examples
  create_xray_examples       = var.create_xray_examples
  common_tags                = local.common_tags
}

# Include AI/ML resources if enabled
module "ai_ml" {
  count  = var.enable_aiml_examples ? 1 : 0
  source = "./modules/ai_ml"
# AWS Sandbox Module

# Input variables are defined in variables.tf

# VPC
resource "aws_vpc" "main" {
  count = var.enable_networking_examples ? 1 : 0

  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = merge(var.default_tags, {
    Name = "${var.project_name}-vpc"
  })
}

# Output configuration details
output "sandbox_configuration" {
  description = "Sandbox configuration details"
  value = {
    project_name = var.project_name
    environment  = var.environment
    region       = var.region
    vpc_id       = var.enable_networking_examples ? aws_vpc.main[0].id : null
    vpc_cidr     = var.vpc_cidr
    resources = {
      compute_enabled    = var.enable_compute_examples
      storage_enabled    = var.enable_storage_examples
      database_enabled   = var.enable_database_examples
      serverless_enabled = var.enable_serverless_examples
      networking_enabled = var.enable_networking_examples
      security_enabled   = var.enable_security_examples
    }
  }
}
  name_prefix               = local.name_prefix
  vpc_id                    = module.vpc.vpc_id
  private_subnet_ids        = module.vpc.private_subnet_ids
  create_sagemaker_examples = var.create_sagemaker_examples
  create_comprehend_examples = var.create_comprehend_examples
  create_rekognition_examples = var.create_rekognition_examples
  common_tags               = local.common_tags
}

# Include DevOps resources if enabled
module "devops" {
  count  = var.enable_devops_examples ? 1 : 0
  source = "./modules/devops"

  name_prefix               = local.name_prefix
  vpc_id                    = module.vpc.vpc_id
  create_codepipeline_examples = var.create_codepipeline_examples
  create_codebuild_examples = var.create_codebuild_examples
  create_codecommit_examples = var.create_codecommit_examples
  common_tags               = local.common_tags
}
