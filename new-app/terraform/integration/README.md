# AWS Terraform Sandbox Integration

This directory contains the integration between the Flask application and the AWS Terraform Sandbox module. It provides a RESTful API to create, manage, and interact with Terraform workspaces that deploy AWS resources using the sandbox module.

## Overview

The integration allows users to:

1. Create Terraform workspaces with customized configurations
2. Plan and apply Terraform configurations to deploy AWS resources
3. View deployed resources and their outputs
4. Destroy resources and delete workspaces
5. Get help information for various AWS resource types

## API Endpoints

### Resource Types

- `GET /api/terraform/resource-types` - Get available AWS resource types for the sandbox

### Workspaces

- `GET /api/terraform/workspaces` - List all Terraform workspaces
- `GET /api/terraform/workspaces/{workspace_id}` - Get details about a specific workspace
- `POST /api/terraform/workspaces` - Create a new Terraform workspace
- `DELETE /api/terraform/workspaces/{workspace_id}` - Delete a workspace

### Workspace Operations

- `POST /api/terraform/workspaces/{workspace_id}/plan` - Run Terraform plan on a workspace
- `POST /api/terraform/workspaces/{workspace_id}/apply` - Run Terraform apply on a workspace
- `POST /api/terraform/workspaces/{workspace_id}/destroy` - Run Terraform destroy on a workspace
- `PUT /api/terraform/workspaces/{workspace_id}/variables` - Update variables for a workspace

### Help Information

- `GET /api/terraform/help/{resource_type}` - Get help information for a specific resource type

## Integration with Flask Application

To integrate the Terraform API with the main Flask application, add the following to your `app.py`:

```python
from terraform.integration import aws_sandbox_api

# Initialize the app
app = Flask(__name__)

# Register the Terraform API blueprint
aws_sandbox_api.init_app(app)
```

## Example Usage

### Creating a workspace

```bash
curl -X POST http://localhost:5000/api/terraform/workspaces \
  -H "Content-Type: application/json" \
  -d '{
    "project_name": "my-sandbox",
    "environment": "dev",
    "region": "us-east-1",
    "create_ec2_examples": true,
    "create_rds_examples": false
  }'
```

### Applying a workspace

```bash
curl -X POST http://localhost:5000/api/terraform/workspaces/workspace-20250905-123456/apply
```

## Requirements

- Terraform CLI must be installed on the server
- AWS credentials must be configured (e.g., via environment variables, AWS CLI profile, or instance profile)
- The Flask application must have permissions to create and manage files in the workspace directory

## Security Considerations

- In production, add proper authentication and authorization to protect these API endpoints
- Consider adding input validation and rate limiting to prevent misuse
- Be aware that Terraform operations can create AWS resources that may incur costs
- Consider setting up AWS budget alerts or using the AWS Free Tier for testing

## Directory Structure

- `aws_sandbox_api.py` - The Flask blueprint with API routes
- `../modules/aws-sandbox` - The main AWS Terraform sandbox module
- `../workspaces` - Directory where Terraform workspaces are stored
