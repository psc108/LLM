# Serverless Module Variables

variable "name_prefix" {
  description = "Prefix to be used in the naming of resources"
  type        = string
}

variable "vpc_id" {
  description = "ID of the VPC"
  type        = string
}

variable "private_subnet_ids" {
  description = "List of private subnet IDs"
  type        = list(string)
}

variable "create_lambda_examples" {
  description = "Whether to create Lambda function examples"
  type        = bool
  default     = true
}

variable "create_apigateway_examples" {
  description = "Whether to create API Gateway examples"
  type        = bool
  default     = true
}

variable "create_stepfunctions_examples" {
  description = "Whether to create Step Functions examples"
  type        = bool
  default     = true
}

variable "common_tags" {
  description = "Common tags to apply to all resources"
  type        = map(string)
  default     = {}
}
