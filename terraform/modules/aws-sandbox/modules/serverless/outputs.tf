# Serverless Module Outputs

output "lambda_function_names" {
  description = "Names of the Lambda functions"
  value = var.create_lambda_examples ? {
    hello_world    = aws_lambda_function.hello_world[0].function_name
    file_processor = aws_lambda_function.file_processor[0].function_name
  } : null
}

output "lambda_function_arns" {
  description = "ARNs of the Lambda functions"
  value = var.create_lambda_examples ? {
    hello_world    = aws_lambda_function.hello_world[0].arn
    file_processor = aws_lambda_function.file_processor[0].arn
  } : null
}

output "api_gateway_endpoints" {
  description = "Endpoints of the API Gateway resources"
  value = var.create_apigateway_examples && var.create_lambda_examples ? {
    base_url = "${aws_api_gateway_deployment.main[0].invoke_url}${aws_api_gateway_stage.main[0].stage_name}"
    hello    = "${aws_api_gateway_deployment.main[0].invoke_url}${aws_api_gateway_stage.main[0].stage_name}/hello"
    files    = "${aws_api_gateway_deployment.main[0].invoke_url}${aws_api_gateway_stage.main[0].stage_name}/files"
  } : null
}

output "api_gateway_id" {
  description = "ID of the API Gateway"
  value       = var.create_apigateway_examples ? aws_api_gateway_rest_api.main[0].id : null
}

output "stepfunctions_state_machine_arns" {
  description = "ARNs of the Step Functions state machines"
  value       = var.create_stepfunctions_examples ? [aws_sfn_state_machine.main[0].arn] : null
}

output "stepfunctions_state_machine_name" {
  description = "Name of the Step Functions state machine"
  value       = var.create_stepfunctions_examples ? aws_sfn_state_machine.main[0].name : null
}

output "lambda_security_group_id" {
  description = "ID of the security group for Lambda functions in VPC"
  value       = aws_security_group.lambda.id
}

output "lambda_role_arn" {
  description = "ARN of the IAM role for Lambda functions"
  value       = aws_iam_role.lambda.arn
}

output "lambda_role_name" {
  description = "Name of the IAM role for Lambda functions"
  value       = aws_iam_role.lambda.name
}
