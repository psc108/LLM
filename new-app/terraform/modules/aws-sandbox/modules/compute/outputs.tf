# Compute Module Outputs

output "bastion_public_ip" {
  description = "Public IP of the bastion host"
  value       = var.create_bastion ? aws_instance.bastion[0].public_ip : null
}

output "bastion_instance_id" {
  description = "Instance ID of the bastion host"
  value       = var.create_bastion ? aws_instance.bastion[0].id : null
}

output "ec2_instance_ids" {
  description = "IDs of the EC2 instances"
  value       = aws_instance.private[*].id
}

output "ec2_private_ips" {
  description = "Private IPs of the EC2 instances"
  value       = aws_instance.private[*].private_ip
}

output "asg_names" {
  description = "Names of the Auto Scaling Groups"
  value       = var.create_asg_examples ? [aws_autoscaling_group.web_app[0].name] : []
}

output "launch_template_id" {
  description = "ID of the Launch Template"
  value       = var.create_asg_examples ? aws_launch_template.web_app[0].id : null
}

output "key_pair_name" {
  description = "Name of the key pair used"
  value       = var.create_key_pair ? aws_key_pair.sandbox[0].key_name : var.key_name
}

output "security_group_internal_id" {
  description = "ID of the internal security group"
  value       = aws_security_group.internal.id
}

output "security_group_bastion_id" {
  description = "ID of the bastion security group"
  value       = var.create_bastion ? aws_security_group.bastion[0].id : null
}

output "iam_role_arn" {
  description = "ARN of the IAM role for EC2"
  value       = aws_iam_role.ec2_ssm.arn
}

output "instance_profile_name" {
  description = "Name of the instance profile"
  value       = aws_iam_instance_profile.ec2_ssm.name
}
