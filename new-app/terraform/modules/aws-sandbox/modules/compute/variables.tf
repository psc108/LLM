# Compute Module Variables

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

variable "public_subnet_ids" {
  description = "List of public subnet IDs"
  type        = list(string)
}

variable "private_subnet_ids" {
  description = "List of private subnet IDs"
  type        = list(string)
}

variable "create_bastion" {
  description = "Whether to create a bastion host"
  type        = bool
  default     = true
}

variable "create_ec2_examples" {
  description = "Whether to create EC2 instance examples"
  type        = bool
  default     = true
}

variable "create_asg_examples" {
  description = "Whether to create Auto Scaling Group examples"
  type        = bool
  default     = true
}

variable "create_ecs_examples" {
  description = "Whether to create ECS examples"
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

variable "common_tags" {
  description = "Common tags to apply to all resources"
  type        = map(string)
  default     = {}
}
