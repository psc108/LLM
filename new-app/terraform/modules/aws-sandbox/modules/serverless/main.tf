# Serverless Module

# IAM Role for Lambda functions
resource "aws_iam_role" "lambda" {
  name = "${var.name_prefix}-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "lambda.amazonaws.com"
      }
    }]
  })

  tags = merge(var.common_tags, {
    Name = "${var.name_prefix}-lambda-role"
  })
}

# Attach basic Lambda execution policy
resource "aws_iam_role_policy_attachment" "lambda_basic" {
  role       = aws_iam_role.lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# Attach VPC access policy for Lambda
resource "aws_iam_role_policy_attachment" "lambda_vpc" {
  role       = aws_iam_role.lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
}

# Create CloudWatch Logs group for Lambda functions
resource "aws_cloudwatch_log_group" "hello_world" {
  count             = var.create_lambda_examples ? 1 : 0
  name              = "/aws/lambda/${var.name_prefix}-hello-world"
  retention_in_days = 7

  tags = merge(var.common_tags, {
    Name = "/aws/lambda/${var.name_prefix}-hello-world"
  })
}

resource "aws_cloudwatch_log_group" "file_processor" {
  count             = var.create_lambda_examples ? 1 : 0
  name              = "/aws/lambda/${var.name_prefix}-file-processor"
  retention_in_days = 7

  tags = merge(var.common_tags, {
    Name = "/aws/lambda/${var.name_prefix}-file-processor"
  })
}

# Security group for Lambda in VPC
resource "aws_security_group" "lambda" {
  name        = "${var.name_prefix}-lambda-sg"
  description = "Security group for Lambda functions in VPC"
  vpc_id      = var.vpc_id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(var.common_tags, {
    Name = "${var.name_prefix}-lambda-sg"
  })
}

# Create Lambda functions
# 1. Simple Hello World Lambda
data "archive_file" "hello_world" {
  count       = var.create_lambda_examples ? 1 : 0
  type        = "zip"
  output_path = "${path.module}/hello_world.zip"

  source {
    content  = <<-EOF
      def handler(event, context):
          print("Hello from Lambda!")
          return {
              'statusCode': 200,
              'headers': {
                  'Content-Type': 'application/json'
              },
              'body': {
                  'message': 'Hello from Lambda!',
                  'event': event,
                  'sandbox': '${var.name_prefix}'
              }
          }
    EOF
    filename = "lambda_function.py"
  }
}

resource "aws_lambda_function" "hello_world" {
  count         = var.create_lambda_examples ? 1 : 0
  function_name = "${var.name_prefix}-hello-world"
  filename      = data.archive_file.hello_world[0].output_path
  handler       = "lambda_function.handler"
  role          = aws_iam_role.lambda.arn
  runtime       = "python3.9"

  memory_size = 128
  timeout     = 30

  environment {
    variables = {
      ENVIRONMENT = "sandbox"
      PREFIX      = var.name_prefix
    }
  }

  depends_on = [aws_cloudwatch_log_group.hello_world]

  tags = merge(var.common_tags, {
    Name = "${var.name_prefix}-hello-world"
  })
}

# 2. File processor Lambda (VPC-connected)
data "archive_file" "file_processor" {
  count       = var.create_lambda_examples ? 1 : 0
  type        = "zip"
  output_path = "${path.module}/file_processor.zip"

  source {
    content  = <<-EOF
      import os
      import json
      import boto3
      from datetime import datetime

      def handler(event, context):
          print(f"Processing event: {json.dumps(event)}")

          s3 = boto3.client('s3')
          current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

          # Example: Process S3 event
          response_data = {
              'timestamp': current_time,
              'function_name': context.function_name,
              'aws_request_id': context.aws_request_id,
              'log_group_name': context.log_group_name,
              'log_stream_name': context.log_stream_name,
              'environment': os.environ.get('ENVIRONMENT'),
              'processed_event': event
          }

          return {
              'statusCode': 200,
              'headers': {
                  'Content-Type': 'application/json'
              },
              'body': json.dumps(response_data)
          }
    EOF
    filename = "lambda_function.py"
  }
}

resource "aws_lambda_function" "file_processor" {
  count         = var.create_lambda_examples ? 1 : 0
  function_name = "${var.name_prefix}-file-processor"
  filename      = data.archive_file.file_processor[0].output_path
  handler       = "lambda_function.handler"
  role          = aws_iam_role.lambda.arn
  runtime       = "python3.9"

  memory_size = 256
  timeout     = 60

  vpc_config {
    subnet_ids         = var.private_subnet_ids
    security_group_ids = [aws_security_group.lambda.id]
  }

  environment {
    variables = {
      ENVIRONMENT = "sandbox"
      PREFIX      = var.name_prefix
    }
  }

  depends_on = [aws_cloudwatch_log_group.file_processor]

  tags = merge(var.common_tags, {
    Name = "${var.name_prefix}-file-processor"
  })
}

# API Gateway resources
resource "aws_api_gateway_rest_api" "main" {
  count       = var.create_apigateway_examples ? 1 : 0
  name        = "${var.name_prefix}-api"
  description = "Sandbox API Gateway"
  endpoint_configuration {
    types = ["REGIONAL"]
  }

  tags = merge(var.common_tags, {
    Name = "${var.name_prefix}-api"
  })
}

# API Gateway resources and methods for hello-world Lambda
resource "aws_api_gateway_resource" "hello" {
  count       = var.create_apigateway_examples && var.create_lambda_examples ? 1 : 0
  parent_id   = aws_api_gateway_rest_api.main[0].root_resource_id
  path_part   = "hello"
  rest_api_id = aws_api_gateway_rest_api.main[0].id
}

resource "aws_api_gateway_method" "hello_get" {
  count         = var.create_apigateway_examples && var.create_lambda_examples ? 1 : 0
  authorization = "NONE"
  http_method   = "GET"
  resource_id   = aws_api_gateway_resource.hello[0].id
  rest_api_id   = aws_api_gateway_rest_api.main[0].id
}

resource "aws_api_gateway_integration" "hello_get" {
  count                   = var.create_apigateway_examples && var.create_lambda_examples ? 1 : 0
  rest_api_id             = aws_api_gateway_rest_api.main[0].id
  resource_id             = aws_api_gateway_resource.hello[0].id
  http_method             = aws_api_gateway_method.hello_get[0].http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.hello_world[0].invoke_arn
}

# API Gateway resources and methods for file-processor Lambda
resource "aws_api_gateway_resource" "files" {
  count       = var.create_apigateway_examples && var.create_lambda_examples ? 1 : 0
  parent_id   = aws_api_gateway_rest_api.main[0].root_resource_id
  path_part   = "files"
  rest_api_id = aws_api_gateway_rest_api.main[0].id
}

resource "aws_api_gateway_method" "files_post" {
  count         = var.create_apigateway_examples && var.create_lambda_examples ? 1 : 0
  authorization = "NONE"
  http_method   = "POST"
  resource_id   = aws_api_gateway_resource.files[0].id
  rest_api_id   = aws_api_gateway_rest_api.main[0].id
}

resource "aws_api_gateway_integration" "files_post" {
  count                   = var.create_apigateway_examples && var.create_lambda_examples ? 1 : 0
  rest_api_id             = aws_api_gateway_rest_api.main[0].id
  resource_id             = aws_api_gateway_resource.files[0].id
  http_method             = aws_api_gateway_method.files_post[0].http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.file_processor[0].invoke_arn
}

# Lambda permissions for API Gateway
resource "aws_lambda_permission" "hello_api" {
  count         = var.create_apigateway_examples && var.create_lambda_examples ? 1 : 0
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.hello_world[0].function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.main[0].execution_arn}/*/*/hello"
}

resource "aws_lambda_permission" "files_api" {
  count         = var.create_apigateway_examples && var.create_lambda_examples ? 1 : 0
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.file_processor[0].function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.main[0].execution_arn}/*/*/files"
}

# Deploy the API Gateway
resource "aws_api_gateway_deployment" "main" {
  count       = var.create_apigateway_examples && var.create_lambda_examples ? 1 : 0
  rest_api_id = aws_api_gateway_rest_api.main[0].id

  depends_on = [
    aws_api_gateway_integration.hello_get,
    aws_api_gateway_integration.files_post
  ]

  # Force a new deployment on each apply
  triggers = {
    redeployment = sha1(jsonencode({
      hello_integration = aws_api_gateway_integration.hello_get[0].id
      files_integration = aws_api_gateway_integration.files_post[0].id
    }))
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_api_gateway_stage" "main" {
  count         = var.create_apigateway_examples && var.create_lambda_examples ? 1 : 0
  deployment_id = aws_api_gateway_deployment.main[0].id
  rest_api_id   = aws_api_gateway_rest_api.main[0].id
  stage_name    = "v1"

  tags = merge(var.common_tags, {
    Name = "${var.name_prefix}-api-stage"
  })
}

# Step Functions state machine (simple example)
resource "aws_sfn_state_machine" "main" {
  count     = var.create_stepfunctions_examples ? 1 : 0
  name      = "${var.name_prefix}-workflow"
  role_arn  = aws_iam_role.step_functions[0].arn
  type      = "STANDARD" # or "EXPRESS" for high-volume, short-duration workloads

  definition = jsonencode({
    Comment = "A simple AWS Step Functions state machine"
    StartAt = "HelloWorld"
    States = {
      HelloWorld = {
        Type = "Task"
        Resource = var.create_lambda_examples ? aws_lambda_function.hello_world[0].arn : "arn:aws:lambda:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:function:dummy"
        Next = "Wait"
        Retry = [
          {
            ErrorEquals = ["States.ALL"]
            IntervalSeconds = 1
            MaxAttempts = 3
            BackoffRate = 2
          }
        ]
      }
      Wait = {
        Type = "Wait"
        Seconds = 10
        Next = "ProcessData"
      }
      ProcessData = {
        Type = "Task"
        Resource = var.create_lambda_examples ? aws_lambda_function.file_processor[0].arn : "arn:aws:lambda:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:function:dummy"
        End = true
        Catch = [
          {
            ErrorEquals = ["States.ALL"]
            Next = "HandleError"
          }
        ]
      }
      HandleError = {
        Type = "Pass"
        Result = {
          error = "An error occurred during processing"
          time = "$$.State.EnteredTime"
        }
        End = true
      }
    }
  })

  tags = merge(var.common_tags, {
    Name = "${var.name_prefix}-workflow"
  })
}

# IAM role for Step Functions
resource "aws_iam_role" "step_functions" {
  count = var.create_stepfunctions_examples ? 1 : 0
  name  = "${var.name_prefix}-step-functions-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "states.amazonaws.com"
      }
    }]
  })

  tags = merge(var.common_tags, {
    Name = "${var.name_prefix}-step-functions-role"
  })
}

# IAM policy for Step Functions to invoke Lambda
resource "aws_iam_policy" "step_functions_lambda" {
  count  = var.create_stepfunctions_examples ? 1 : 0
  name   = "${var.name_prefix}-step-functions-lambda-policy"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action   = "lambda:InvokeFunction"
      Effect   = "Allow"
      Resource = "*"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "step_functions_lambda" {
  count      = var.create_stepfunctions_examples ? 1 : 0
  role       = aws_iam_role.step_functions[0].name
  policy_arn = aws_iam_policy.step_functions_lambda[0].arn
}

# Step Functions event rule (trigger every day at 12:00 UTC)
resource "aws_cloudwatch_event_rule" "daily_workflow" {
  count               = var.create_stepfunctions_examples ? 1 : 0
  name                = "${var.name_prefix}-daily-workflow"
  description         = "Triggers the workflow state machine daily"
  schedule_expression = "cron(0 12 * * ? *)"
  is_enabled          = false # Disabled by default

  tags = merge(var.common_tags, {
    Name = "${var.name_prefix}-daily-workflow-rule"
  })
}

resource "aws_cloudwatch_event_target" "daily_workflow" {
  count     = var.create_stepfunctions_examples ? 1 : 0
  rule      = aws_cloudwatch_event_rule.daily_workflow[0].name
  arn       = aws_sfn_state_machine.main[0].arn
  role_arn  = aws_iam_role.events[0].arn
}

# IAM role for CloudWatch Events
resource "aws_iam_role" "events" {
  count = var.create_stepfunctions_examples ? 1 : 0
  name  = "${var.name_prefix}-events-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "events.amazonaws.com"
      }
    }]
  })

  tags = merge(var.common_tags, {
    Name = "${var.name_prefix}-events-role"
  })
}

resource "aws_iam_policy" "events_sfn" {
  count  = var.create_stepfunctions_examples ? 1 : 0
  name   = "${var.name_prefix}-events-sfn-policy"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action   = "states:StartExecution"
      Effect   = "Allow"
      Resource = aws_sfn_state_machine.main[0].arn
    }]
  })
}

resource "aws_iam_role_policy_attachment" "events_sfn" {
  count      = var.create_stepfunctions_examples ? 1 : 0
  role       = aws_iam_role.events[0].name
  policy_arn = aws_iam_policy.events_sfn[0].arn
}

# Get current region and account ID for ARN construction
data "aws_region" "current" {}
data "aws_caller_identity" "current" {}
