# Database Module Variables

variable "name_prefix" {
  description = "Prefix to be used in the naming of resources"
  type        = string
}

variable "vpc_id" {
  description = "ID of the VPC"
  type        = string
}

variable "vpc_cidr" {
  description = "CIDR block of the VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "database_subnet_ids" {
  description = "List of database subnet IDs"
  type        = list(string)
}

variable "create_rds_examples" {
  description = "Whether to create RDS instance examples"
  type        = bool
  default     = true
}

variable "create_dynamodb_examples" {
  description = "Whether to create DynamoDB examples"
  type        = bool
  default     = true
}

variable "rds_instance_class" {
  description = "Instance class for RDS instances"
  type        = string
  default     = "db.t3.micro"
}

variable "common_tags" {
  description = "Common tags to apply to all resources"
  type        = map(string)
  default     = {}
}
