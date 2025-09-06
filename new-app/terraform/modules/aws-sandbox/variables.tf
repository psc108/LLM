# AWS Terraform Sandbox Module Variables
# Variables for AWS sandbox module

variable "project_name" {
  description = "Project name to use in resource naming"
  type        = string
  default     = "terraform-sandbox"
}

variable "environment" {
  description = "Environment name (e.g. dev, staging, prod)"
  type        = string
  default     = "dev"
}

variable "region" {
  description = "AWS region to deploy resources"
  type        = string
  default     = "us-east-1"
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "create_nat_gateway" {
  description = "Create NAT Gateway for private subnets (incurs costs)"
  type        = bool
  default     = false
}

variable "enable_vpc_flow_logs" {
  description = "Enable VPC Flow Logs to CloudWatch"
  type        = bool
  default     = true
}

# Compute Options
variable "enable_compute_examples" {
  description = "Enable compute resource examples"
  type        = bool
  default     = true
}

variable "create_bastion" {
  description = "Create a bastion host in a public subnet"
  type        = bool
  default     = true
}

variable "create_ec2_examples" {
  description = "Create EC2 instance examples"
  type        = bool
  default     = true
}

# Database Options
variable "enable_database_examples" {
  description = "Enable database resource examples"
  type        = bool
  default     = true
}

variable "create_rds_examples" {
  description = "Create RDS instance examples"
  type        = bool
  default     = true
}

variable "create_dynamodb_examples" {
  description = "Create DynamoDB examples"
  type        = bool
  default     = true
}

# Storage Options
variable "enable_storage_examples" {
  description = "Enable storage resource examples"
  type        = bool
  default     = true
}

variable "create_s3_examples" {
  description = "Create S3 bucket examples"
  type        = bool
  default     = true
}

variable "create_efs_examples" {
  description = "Create EFS examples"
  type        = bool
  default     = true
}

# Serverless Options
variable "enable_serverless_examples" {
  description = "Enable serverless resource examples"
  type        = bool
  default     = true
}

variable "create_lambda_examples" {
  description = "Create Lambda function examples"
  type        = bool
  default     = true
}

variable "create_apigateway_examples" {
  description = "Create API Gateway examples"
  type        = bool
  default     = true
}

variable "create_stepfunctions_examples" {
  description = "Create Step Functions examples"
  type        = bool
  default     = true
}

# Security Options
variable "enable_security_examples" {
  description = "Enable security resource examples"
  type        = bool
  default     = true
}

# Networking Options
variable "enable_networking_examples" {
  description = "Enable networking resource examples"
  type        = bool
  default     = true
}

# Container Options
variable "enable_container_examples" {
  description = "Enable container resource examples"
  type        = bool
  default     = true
}

# Monitoring Options
variable "enable_monitoring_examples" {
  description = "Enable monitoring resource examples"
  type        = bool
  default     = true
}

# AI/ML Options
variable "enable_aiml_examples" {
  description = "Enable AI/ML resource examples"
  type        = bool
  default     = true
}

# DevOps Options
variable "enable_devops_examples" {
  description = "Enable DevOps resource examples"
  type        = bool
  default     = true
}

# Tags
variable "default_tags" {
  description = "Default tags to apply to all resources"
  type        = map(string)
  default     = {}
}
# General settings
variable "region" {
  description = "AWS region to deploy resources"
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Project name to use in resource naming"
  type        = string
  default     = "terraform-sandbox"
}

variable "environment" {
  description = "Environment name (e.g. dev, staging, prod)"
  type        = string
  default     = "dev"
}

variable "aws_profile" {
  description = "AWS CLI profile name to use (leave blank for default)"
  type        = string
  default     = ""
}

variable "assume_role_arn" {
  description = "ARN of role to assume for cross-account deployment (leave blank to use profile credentials directly)"
  type        = string
  default     = ""
}

variable "created_by" {
  description = "Creator identifier (user or system ID) for tagging"
  type        = string
  default     = "terraform-sandbox"
}

variable "sandbox_ttl_hours" {
  description = "Time-to-live for sandbox resources in hours (used for tagging)"
  type        = number
  default     = 24
}

variable "default_tags" {
  description = "Default resource tags"
  type        = map(string)
  default     = {}
}

# VPC Settings
variable "vpc_cidr" {
  description = "CIDR block for the VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "azs" {
  description = "Availability Zones to use (if empty, module will choose based on region)"
  type        = list(string)
  default     = []
}

variable "public_subnet_cidrs" {
  description = "CIDR blocks for public subnets"
  type        = list(string)
  default     = ["10.0.1.0/24", "10.0.2.0/24", "10.0.3.0/24"]
}

variable "private_subnet_cidrs" {
  description = "CIDR blocks for private subnets"
  type        = list(string)
  default     = ["10.0.11.0/24", "10.0.12.0/24", "10.0.13.0/24"]
}

variable "database_subnet_cidrs" {
  description = "CIDR blocks for database subnets"
  type        = list(string)
  default     = ["10.0.21.0/24", "10.0.22.0/24", "10.0.23.0/24"]
}

variable "create_nat_gateway" {
  description = "Create NAT Gateway for private subnets (incurs costs)"
  type        = bool
  default     = true
}

variable "enable_vpn_gateway" {
  description = "Enable Virtual Private Gateway"
  type        = bool
  default     = false
}

variable "enable_vpc_flow_logs" {
  description = "Enable VPC Flow Logs to CloudWatch"
  type        = bool
  default     = true
}

# Compute Options
variable "enable_compute_examples" {
  description = "Enable compute resource examples"
  type        = bool
  default     = true
}

variable "create_bastion" {
  description = "Create a bastion host in a public subnet"
  type        = bool
  default     = true
}

variable "create_ec2_examples" {
  description = "Create EC2 instance examples"
  type        = bool
  default     = true
}

variable "create_asg_examples" {
  description = "Create Auto Scaling Group examples"
  type        = bool
  default     = true
}

variable "instance_type" {
  description = "EC2 instance type"
  type        = string
  default     = "t3.micro"
}

variable "create_key_pair" {
  description = "Create an EC2 key pair for SSH access"
  type        = bool
  default     = false
}

variable "key_name" {
  description = "EC2 key pair name (new or existing)"
  type        = string
  default     = ""
}

variable "ssh_public_key" {
  description = "SSH public key for EC2 key pair (if create_key_pair is true)"
  type        = string
  default     = ""
}

# Database Options
variable "enable_database_examples" {
  description = "Enable database resource examples"
  type        = bool
  default     = true
}

variable "create_rds_examples" {
  description = "Create RDS instance examples"
  type        = bool
  default     = true
}

variable "create_dynamodb_examples" {
  description = "Create DynamoDB examples"
  type        = bool
  default     = true
}

variable "rds_instance_class" {
  description = "Instance class for RDS instances"
  type        = string
  default     = "db.t3.micro"
}

# Storage Options
variable "enable_storage_examples" {
  description = "Enable storage resource examples"
  type        = bool
  default     = true
}

variable "create_s3_examples" {
  description = "Create S3 bucket examples"
  type        = bool
  default     = true
}

variable "create_efs_examples" {
  description = "Create EFS examples"
  type        = bool
  default     = true
}

# Serverless Options
variable "enable_serverless_examples" {
  description = "Enable serverless resource examples"
  type        = bool
  default     = true
}

variable "create_lambda_examples" {
  description = "Create Lambda function examples"
  type        = bool
  default     = true
}

variable "create_apigateway_examples" {
  description = "Create API Gateway examples"
  type        = bool
  default     = true
}

variable "create_stepfunctions_examples" {
  description = "Create Step Functions examples"
  type        = bool
  default     = true
}

# Security Options
variable "enable_security_examples" {
  description = "Enable security resource examples"
  type        = bool
  default     = true
}

variable "create_iam_examples" {
  description = "Create IAM examples"
  type        = bool
  default     = true
}

variable "create_kms_examples" {
  description = "Create KMS examples"
  type        = bool
  default     = true
}

variable "create_waf_examples" {
  description = "Create WAF examples"
  type        = bool
  default     = true
}

variable "create_securityhub_examples" {
  description = "Create SecurityHub examples"
  type        = bool
  default     = true
}

# Networking Options
variable "enable_networking_examples" {
  description = "Enable networking resource examples"
  type        = bool
  default     = true
}

variable "create_route53_examples" {
  description = "Create Route 53 examples"
  type        = bool
  default     = true
}

variable "create_cloudfront_examples" {
  description = "Create CloudFront examples"
  type        = bool
  default     = true
}

variable "create_elb_examples" {
  description = "Create ELB examples"
  type        = bool
  default     = true
}

variable "create_vpce_examples" {
  description = "Create VPC Endpoint examples"
  type        = bool
  default     = true
}

# Container Options
variable "enable_container_examples" {
  description = "Enable container resource examples"
  type        = bool
  default     = true
}

variable "create_ecr_examples" {
  description = "Create ECR examples"
  type        = bool
  default     = true
}

variable "create_eks_examples" {
  description = "Create EKS examples"
  type        = bool
  default     = true
}

variable "create_ecs_examples" {
  description = "Create ECS examples"
  type        = bool
  default     = true
}

# Monitoring Options
variable "enable_monitoring_examples" {
  description = "Enable monitoring resource examples"
  type        = bool
  default     = true
}

variable "create_cloudwatch_examples" {
  description = "Create CloudWatch examples"
  type        = bool
  default     = true
}

variable "create_xray_examples" {
  description = "Create X-Ray examples"
  type        = bool
  default     = true
}

# AI/ML Options
variable "enable_aiml_examples" {
  description = "Enable AI/ML resource examples"
  type        = bool
  default     = true
}

variable "create_sagemaker_examples" {
  description = "Create SageMaker examples"
  type        = bool
  default     = true
}

variable "create_comprehend_examples" {
  description = "Create Comprehend examples"
  type        = bool
  default     = true
}

variable "create_rekognition_examples" {
  description = "Create Rekognition examples"
  type        = bool
  default     = true
}

# DevOps Options
variable "enable_devops_examples" {
  description = "Enable DevOps resource examples"
  type        = bool
  default     = true
}

variable "create_codepipeline_examples" {
  description = "Create CodePipeline examples"
  type        = bool
  default     = true
}

variable "create_codebuild_examples" {
  description = "Create CodeBuild examples"
  type        = bool
  default     = true
}

variable "create_codecommit_examples" {
  description = "Create CodeCommit examples"
  type        = bool
  default     = true
}
