# Storage Module Variables

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

variable "private_subnet_ids" {
  description = "List of private subnet IDs"
  type        = list(string)
}

variable "create_s3_examples" {
  description = "Whether to create S3 bucket examples"
  type        = bool
  default     = true
}

variable "create_efs_examples" {
  description = "Whether to create EFS examples"
  type        = bool
  default     = true
}

variable "common_tags" {
  description = "Common tags to apply to all resources"
  type        = map(string)
  default     = {}
}
