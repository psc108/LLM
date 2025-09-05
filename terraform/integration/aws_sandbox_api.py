import os
import json
import logging
import subprocess
import tempfile
import shutil
from datetime import datetime
from flask import Blueprint, request, jsonify, current_app

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create Blueprint
terraform_bp = Blueprint('terraform', __name__)

# Constants
TERRAFORM_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'terraform')
WORKSPACE_DIR = os.path.join(TERRAFORM_DIR, 'workspaces')

# Ensure workspace directory exists
os.makedirs(WORKSPACE_DIR, exist_ok=True)

# Define resource types that we can help with
RESOURCE_TYPES = {
    'compute': {
        'ec2': 'Amazon EC2 Instances',
        'asg': 'Auto Scaling Groups',
        'bastion': 'Bastion Hosts'
    },
    'storage': {
        's3': 'Amazon S3 Buckets',
        'efs': 'Elastic File System'
    },
    'database': {
        'rds': 'Amazon RDS Databases',
        'dynamodb': 'DynamoDB Tables'
    },
    'serverless': {
        'lambda': 'AWS Lambda Functions',
        'apigateway': 'API Gateway',
        'stepfunctions': 'Step Functions'
    },
    'security': {
        'iam': 'IAM Roles and Policies',
        'kms': 'KMS Keys',
        'waf': 'WAF Rules',
        'securityhub': 'Security Hub'
    },
    'networking': {
        'vpc': 'Virtual Private Cloud',
        'route53': 'Route 53 DNS',
        'cloudfront': 'CloudFront CDN',
        'elb': 'Elastic Load Balancers'
    },
    'containers': {
        'ecr': 'Elastic Container Registry',
        'eks': 'Elastic Kubernetes Service',
        'ecs': 'Elastic Container Service'
    },
    'monitoring': {
        'cloudwatch': 'CloudWatch Monitoring',
        'xray': 'X-Ray Tracing'
    },
    'ai_ml': {
        'sagemaker': 'SageMaker Notebooks',
        'comprehend': 'Comprehend Text Analysis',
        'rekognition': 'Rekognition Image Analysis'
    },
    'devops': {
        'codepipeline': 'CodePipeline',
        'codebuild': 'CodeBuild',
        'codecommit': 'CodeCommit'
    }
}

# Helper Functions
def run_terraform_command(workspace_id, command, extra_args=None):
    """Run a terraform command in the specified workspace"""
    workspace_path = os.path.join(WORKSPACE_DIR, workspace_id)

    if not os.path.exists(workspace_path):
        os.makedirs(workspace_path, exist_ok=True)

    # Build the command
    tf_cmd = ['terraform', command]
    if extra_args:
        tf_cmd.extend(extra_args)

    # Run the command
    try:
        logger.info(f"Running terraform command in {workspace_path}: {' '.join(tf_cmd)}")
        process = subprocess.Popen(
            tf_cmd,
            cwd=workspace_path,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )
        stdout, stderr = process.communicate()

        result = {
            'command': ' '.join(tf_cmd),
            'exit_code': process.returncode,
            'stdout': stdout,
            'stderr': stderr,
            'workspace_id': workspace_id
        }

        if process.returncode != 0:
            logger.error(f"Terraform command failed: {stderr}")
            result['success'] = False
        else:
            result['success'] = True

        return result
    except Exception as e:
        logger.error(f"Error running terraform command: {e}")
        return {
            'command': ' '.join(tf_cmd),
            'success': False,
            'error': str(e),
            'workspace_id': workspace_id
        }

def create_terraform_files(workspace_id, variables):
    """Create terraform configuration files in the workspace directory"""
    workspace_path = os.path.join(WORKSPACE_DIR, workspace_id)

    # Create main.tf that references the sandbox module
    main_tf_content = """
# Main Terraform configuration for AWS sandbox
terraform {
  required_version = ">= 1.0.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 4.0"
    }
    random = {
      source  = "hashicorp/random"
      version = ">= 3.0"
    }
  }
}

provider "aws" {
  region = var.region
}

module "aws_sandbox" {
  source = "../../modules/aws-sandbox"

  # Pass through all variables
  project_name = var.project_name
  environment  = var.environment
  region       = var.region

  # VPC settings
  vpc_cidr                = var.vpc_cidr
  create_nat_gateway      = var.create_nat_gateway
  enable_vpc_flow_logs    = var.enable_vpc_flow_logs

  # Compute options
  enable_compute_examples = var.enable_compute_examples
  create_bastion          = var.create_bastion
  create_ec2_examples     = var.create_ec2_examples

  # Database options
  enable_database_examples  = var.enable_database_examples
  create_rds_examples       = var.create_rds_examples
  create_dynamodb_examples  = var.create_dynamodb_examples

  # Storage options
  enable_storage_examples = var.enable_storage_examples
  create_s3_examples      = var.create_s3_examples
  create_efs_examples     = var.create_efs_examples

  # Serverless options
  enable_serverless_examples     = var.enable_serverless_examples
  create_lambda_examples         = var.create_lambda_examples
  create_apigateway_examples     = var.create_apigateway_examples
  create_stepfunctions_examples  = var.create_stepfunctions_examples

  # Other resource categories
  enable_security_examples    = var.enable_security_examples
  enable_networking_examples  = var.enable_networking_examples
  enable_container_examples   = var.enable_container_examples
  enable_monitoring_examples  = var.enable_monitoring_examples
  enable_aiml_examples        = var.enable_aiml_examples
  enable_devops_examples      = var.enable_devops_examples

  # Common tags
  default_tags = {
    CreatedBy       = "terraform-sandbox-api"
    WorkspaceID     = "${workspace_id}"
    CreationDate    = "${datetime.now().strftime('%Y-%m-%d')}"
    ManagedBy       = "terraform"
  }
}

# Output all sandbox results
output "sandbox_info" {
  description = "Complete sandbox information"
  value       = module.aws_sandbox.sandbox_configuration
}
"""

    # Create variables.tf to define all possible variables
    variables_tf_content = """
# Variables for AWS sandbox configuration

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
"""

    # Create terraform.tfvars with the provided variables
    tfvars_content = ""
    for key, value in variables.items():
        if isinstance(value, bool):
            tfvars_content += f"{key} = {str(value).lower()}\n"
        elif isinstance(value, (int, float)):
            tfvars_content += f"{key} = {value}\n"
        else:
            tfvars_content += f"{key} = \"{value}\"\n"

    # Write the files
    os.makedirs(workspace_path, exist_ok=True)

    with open(os.path.join(workspace_path, 'main.tf'), 'w') as f:
        f.write(main_tf_content)

    with open(os.path.join(workspace_path, 'variables.tf'), 'w') as f:
        f.write(variables_tf_content)

    with open(os.path.join(workspace_path, 'terraform.tfvars'), 'w') as f:
        f.write(tfvars_content)

    return {
        'workspace_id': workspace_id,
        'files_created': ['main.tf', 'variables.tf', 'terraform.tfvars']
    }

# API Routes
@terraform_bp.route('/resource-types', methods=['GET'])
def get_resource_types():
    """Get the available AWS resource types for the sandbox"""
    return jsonify({
        'success': True,
        'resource_types': RESOURCE_TYPES
    })

import os
import json
from datetime import datetime
from flask import jsonify, request, render_template, Blueprint

# Make sure necessary directories exist
os.makedirs(WORKSPACE_DIR, exist_ok=True)

@terraform_bp.route('/sandbox', methods=['GET'])
def sandbox_home():
    """Terraform sandbox home page"""
    return render_template('terraform/sandbox.html', title="Terraform Sandbox")

@terraform_bp.route('/workspaces', methods=['GET'])
def list_workspaces():
    """List all terraform workspaces"""
    try:
        workspaces = []
        for workspace_id in os.listdir(WORKSPACE_DIR):
            workspace_path = os.path.join(WORKSPACE_DIR, workspace_id)
            if os.path.isdir(workspace_path):
                # Read terraform.tfvars to get configuration
                tfvars_path = os.path.join(workspace_path, 'terraform.tfvars')
                config = {}
                if os.path.exists(tfvars_path):
                    with open(tfvars_path, 'r') as f:
                        for line in f:
                            if '=' in line:
                                key, value = line.split('=', 1)
                                config[key.strip()] = value.strip().strip('\"')

                # Get workspace status
                tf_state_path = os.path.join(workspace_path, 'terraform.tfstate')
                status = 'initialized'
                if os.path.exists(tf_state_path):
                    status = 'applied'

                workspaces.append({
                    'workspace_id': workspace_id,
                    'created_at': datetime.fromtimestamp(os.path.getctime(workspace_path)).isoformat(),
                    'status': status,
                    'config': config
                })

        return jsonify({
            'success': True,
            'workspaces': workspaces
        })
    except Exception as e:
        logger.error(f"Error listing workspaces: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@terraform_bp.route('/workspaces/<workspace_id>', methods=['GET'])
def get_workspace(workspace_id):
    """Get details about a specific workspace"""
    try:
        workspace_path = os.path.join(WORKSPACE_DIR, workspace_id)
        if not os.path.exists(workspace_path):
            return jsonify({
                'success': False,
                'error': f'Workspace {workspace_id} not found'
            }), 404

        # Read terraform.tfvars to get configuration
        tfvars_path = os.path.join(workspace_path, 'terraform.tfvars')
        config = {}
        if os.path.exists(tfvars_path):
            with open(tfvars_path, 'r') as f:
                for line in f:
                    if '=' in line:
                        key, value = line.split('=', 1)
                        config[key.strip()] = value.strip().strip('\"')

        # Get workspace status
        tf_state_path = os.path.join(workspace_path, 'terraform.tfstate')
        status = 'initialized'
        outputs = {}
        resources = []

        if os.path.exists(tf_state_path):
            status = 'applied'
            try:
                with open(tf_state_path, 'r') as f:
                    state = json.load(f)
                    if 'outputs' in state:
                        outputs = state['outputs']
                    if 'resources' in state:
                        resources = [{
                            'type': r.get('type', ''),
                            'name': r.get('name', ''),
                            'provider': r.get('provider', ''),
                            'module': r.get('module', 'root')
                        } for r in state.get('resources', [])]
            except Exception as e:
                logger.error(f"Error reading terraform state: {e}")

        return jsonify({
            'success': True,
            'workspace': {
                'workspace_id': workspace_id,
                'created_at': datetime.fromtimestamp(os.path.getctime(workspace_path)).isoformat(),
                'status': status,
                'config': config,
                'outputs': outputs,
                'resources': resources,
                'files': [f for f in os.listdir(workspace_path) if os.path.isfile(os.path.join(workspace_path, f))]
            }
        })
    except Exception as e:
        logger.error(f"Error getting workspace: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@terraform_bp.route('/workspaces', methods=['POST'])
def create_workspace():
    """Create a new terraform workspace"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': 'No data provided'
            }), 400

        # Generate workspace ID if not provided
        workspace_id = data.get('workspace_id', f"workspace-{datetime.now().strftime('%Y%m%d-%H%M%S')}")

        # Check if workspace already exists
        workspace_path = os.path.join(WORKSPACE_DIR, workspace_id)
        if os.path.exists(workspace_path):
            return jsonify({
                'success': False,
                'error': f'Workspace {workspace_id} already exists'
            }), 409

        # Process variables
        variables = {
            'project_name': data.get('project_name', 'terraform-sandbox'),
            'environment': data.get('environment', 'dev'),
            'region': data.get('region', 'us-east-1'),

            # Set defaults for all variables
            'vpc_cidr': data.get('vpc_cidr', '10.0.0.0/16'),
            'create_nat_gateway': data.get('create_nat_gateway', False),
            'enable_vpc_flow_logs': data.get('enable_vpc_flow_logs', True),

            'enable_compute_examples': data.get('enable_compute_examples', True),
            'create_bastion': data.get('create_bastion', True),
            'create_ec2_examples': data.get('create_ec2_examples', True),

            'enable_database_examples': data.get('enable_database_examples', True),
            'create_rds_examples': data.get('create_rds_examples', True),
            'create_dynamodb_examples': data.get('create_dynamodb_examples', True),

            'enable_storage_examples': data.get('enable_storage_examples', True),
            'create_s3_examples': data.get('create_s3_examples', True),
            'create_efs_examples': data.get('create_efs_examples', True),

            'enable_serverless_examples': data.get('enable_serverless_examples', True),
            'create_lambda_examples': data.get('create_lambda_examples', True),
            'create_apigateway_examples': data.get('create_apigateway_examples', True),
            'create_stepfunctions_examples': data.get('create_stepfunctions_examples', True),

            'enable_security_examples': data.get('enable_security_examples', True),
            'enable_networking_examples': data.get('enable_networking_examples', True),
            'enable_container_examples': data.get('enable_container_examples', True),
            'enable_monitoring_examples': data.get('enable_monitoring_examples', True),
            'enable_aiml_examples': data.get('enable_aiml_examples', True),
            'enable_devops_examples': data.get('enable_devops_examples', True),
        }

        # Create terraform files
        result = create_terraform_files(workspace_id, variables)

        # Initialize terraform
        init_result = run_terraform_command(workspace_id, 'init')
        if not init_result['success']:
            return jsonify({
                'success': False,
                'error': 'Failed to initialize terraform',
                'details': init_result
            }), 500

        return jsonify({
            'success': True,
            'message': f'Workspace {workspace_id} created and initialized',
            'workspace_id': workspace_id,
            'variables': variables,
            'init_result': init_result
        })
    except Exception as e:
        logger.error(f"Error creating workspace: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@terraform_bp.route('/workspaces/<workspace_id>/plan', methods=['POST'])
def plan_workspace(workspace_id):
    """Run terraform plan on a workspace"""
    try:
        workspace_path = os.path.join(WORKSPACE_DIR, workspace_id)
        if not os.path.exists(workspace_path):
            return jsonify({
                'success': False,
                'error': f'Workspace {workspace_id} not found'
            }), 404

        # Run terraform plan
        plan_result = run_terraform_command(workspace_id, 'plan', ['-detailed-exitcode', '-out=tfplan'])

        # Check result
        if plan_result['exit_code'] == 0:
            plan_status = 'no_changes'
        elif plan_result['exit_code'] == 2:
            plan_status = 'changes'
        else:
            plan_status = 'error'

        return jsonify({
            'success': plan_result['exit_code'] in [0, 2],  # 0=no changes, 2=changes
            'plan_status': plan_status,
            'plan_output': plan_result['stdout'],
            'error': plan_result['stderr'] if plan_status == 'error' else None,
            'workspace_id': workspace_id
        })
    except Exception as e:
        logger.error(f"Error planning workspace: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@terraform_bp.route('/workspaces/<workspace_id>/apply', methods=['POST'])
def apply_workspace(workspace_id):
    """Run terraform apply on a workspace"""
    try:
        workspace_path = os.path.join(WORKSPACE_DIR, workspace_id)
        if not os.path.exists(workspace_path):
            return jsonify({
                'success': False,
                'error': f'Workspace {workspace_id} not found'
            }), 404

        # Check if plan exists and use it if it does
        plan_file = os.path.join(workspace_path, 'tfplan')
        extra_args = ['-auto-approve']
        if os.path.exists(plan_file):
            extra_args = ['tfplan']

        # Run terraform apply
        apply_result = run_terraform_command(workspace_id, 'apply', extra_args)

        # Get outputs if successful
        outputs = None
        if apply_result['success']:
            output_result = run_terraform_command(workspace_id, 'output', ['-json'])
            if output_result['success']:
                try:
                    outputs = json.loads(output_result['stdout'])
                except Exception as e:
                    logger.error(f"Error parsing terraform outputs: {e}")

        return jsonify({
            'success': apply_result['success'],
            'apply_output': apply_result['stdout'],
            'error': apply_result['stderr'] if not apply_result['success'] else None,
            'outputs': outputs,
            'workspace_id': workspace_id
        })
    except Exception as e:
        logger.error(f"Error applying workspace: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@terraform_bp.route('/workspaces/<workspace_id>/destroy', methods=['POST'])
def destroy_workspace(workspace_id):
    """Run terraform destroy on a workspace"""
    try:
        workspace_path = os.path.join(WORKSPACE_DIR, workspace_id)
        if not os.path.exists(workspace_path):
            return jsonify({
                'success': False,
                'error': f'Workspace {workspace_id} not found'
            }), 404

        # Run terraform destroy
        destroy_result = run_terraform_command(workspace_id, 'destroy', ['-auto-approve'])

        return jsonify({
            'success': destroy_result['success'],
            'destroy_output': destroy_result['stdout'],
            'error': destroy_result['stderr'] if not destroy_result['success'] else None,
            'workspace_id': workspace_id
        })
    except Exception as e:
        logger.error(f"Error destroying workspace: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@terraform_bp.route('/workspaces/<workspace_id>', methods=['DELETE'])
def delete_workspace(workspace_id):
    """Delete a workspace (optionally destroying resources first)"""
    try:
        workspace_path = os.path.join(WORKSPACE_DIR, workspace_id)
        if not os.path.exists(workspace_path):
            return jsonify({
                'success': False,
                'error': f'Workspace {workspace_id} not found'
            }), 404

        # Check if we should destroy resources first
        destroy_first = request.args.get('destroy', 'false').lower() == 'true'
        destroy_result = None

        if destroy_first:
            destroy_result = run_terraform_command(workspace_id, 'destroy', ['-auto-approve'])
            if not destroy_result['success']:
                return jsonify({
                    'success': False,
                    'error': 'Failed to destroy resources',
                    'destroy_result': destroy_result,
                    'workspace_id': workspace_id
                }), 500

        # Delete the workspace directory
        shutil.rmtree(workspace_path)

        return jsonify({
            'success': True,
            'message': f'Workspace {workspace_id} deleted',
            'destroy_result': destroy_result,
            'workspace_id': workspace_id
        })
    except Exception as e:
        logger.error(f"Error deleting workspace: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@terraform_bp.route('/workspaces/<workspace_id>/variables', methods=['PUT'])
def update_workspace_variables(workspace_id):
    """Update variables for a workspace"""
    try:
        workspace_path = os.path.join(WORKSPACE_DIR, workspace_id)
        if not os.path.exists(workspace_path):
            return jsonify({
                'success': False,
                'error': f'Workspace {workspace_id} not found'
            }), 404

        # Get updated variables
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': 'No data provided'
            }), 400

        # Read current variables
        tfvars_path = os.path.join(workspace_path, 'terraform.tfvars')
        current_vars = {}
        if os.path.exists(tfvars_path):
            with open(tfvars_path, 'r') as f:
                for line in f:
                    if '=' in line:
                        key, value = line.split('=', 1)
                        current_vars[key.strip()] = value.strip()

        # Update variables with new values
        updated_vars = current_vars.copy()
        for key, value in data.items():
            if isinstance(value, bool):
                updated_vars[key] = str(value).lower()
            elif isinstance(value, (int, float)):
                updated_vars[key] = str(value)
            else:
                updated_vars[key] = f'"{value}"'

        # Write updated tfvars
        with open(tfvars_path, 'w') as f:
            for key, value in updated_vars.items():
                f.write(f"{key} = {value}\n")

        return jsonify({
            'success': True,
            'message': f'Variables updated for workspace {workspace_id}',
            'variables': {k: v.strip('"') for k, v in updated_vars.items()},
            'workspace_id': workspace_id
        })
    except Exception as e:
        logger.error(f"Error updating workspace variables: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@terraform_bp.route('/help/<resource_type>', methods=['GET'])
def get_resource_help(resource_type):
    """Get help information for a specific resource type"""
    try:
        # Split resource_type if it contains a subtype (e.g. "compute/ec2")
        parts = resource_type.split('/')
        category = parts[0]
        resource = parts[1] if len(parts) > 1 else None

        # Basic help information
        help_data = {
            'resource_type': resource_type,
            'description': '',
            'terraform_examples': [],
            'documentation_links': []
        }

        # Provide help based on resource type
        if category == 'compute':
            help_data['description'] = 'AWS compute resources like EC2, Auto Scaling Groups, and more'

            if resource == 'ec2' or resource is None:
                help_data['terraform_examples'].append('''
# Basic EC2 instance example
resource "aws_instance" "example" {
  ami           = "ami-0c55b159cbfafe1f0"
  instance_type = "t3.micro"
  tags = {
    Name = "example-instance"
  }
}
''')
                help_data['documentation_links'].append({
                    'title': 'AWS EC2 Instance Documentation',
                    'url': 'https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/instance'
                })

            if resource == 'asg' or resource is None:
                help_data['terraform_examples'].append('''
# Auto Scaling Group example
resource "aws_launch_template" "example" {
  name_prefix   = "example"
  image_id      = "ami-0c55b159cbfafe1f0"
  instance_type = "t3.micro"
}

resource "aws_autoscaling_group" "example" {
  availability_zones = ["us-east-1a"]
  desired_capacity   = 1
  max_size           = 3
  min_size           = 1

  launch_template {
    id      = aws_launch_template.example.id
    version = "$Latest"
  }
}
''')
                help_data['documentation_links'].append({
                    'title': 'AWS Auto Scaling Group Documentation',
                    'url': 'https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/autoscaling_group'
                })

        elif category == 'storage':
            help_data['description'] = 'AWS storage resources like S3, EFS, and more'

            if resource == 's3' or resource is None:
                help_data['terraform_examples'].append('''
# S3 bucket example
resource "aws_s3_bucket" "example" {
  bucket = "my-example-bucket"
  tags = {
    Name = "My example bucket"
  }
}

resource "aws_s3_bucket_acl" "example" {
  bucket = aws_s3_bucket.example.id
  acl    = "private"
}
''')
                help_data['documentation_links'].append({
                    'title': 'AWS S3 Bucket Documentation',
                    'url': 'https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/s3_bucket'
                })

        elif category == 'database':
            help_data['description'] = 'AWS database resources like RDS, DynamoDB, and more'

            if resource == 'rds' or resource is None:
                help_data['terraform_examples'].append('''
# RDS instance example
resource "aws_db_instance" "example" {
  allocated_storage    = 10
  engine               = "mysql"
  engine_version       = "5.7"
  instance_class       = "db.t3.micro"
  name                 = "mydb"
  username             = "admin"
  password             = "password"
  parameter_group_name = "default.mysql5.7"
  skip_final_snapshot  = true
}
''')
                help_data['documentation_links'].append({
                    'title': 'AWS RDS Instance Documentation',
                    'url': 'https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/db_instance'
                })

        elif category == 'serverless':
            help_data['description'] = 'AWS serverless resources like Lambda, API Gateway, and more'

            if resource == 'lambda' or resource is None:
                help_data['terraform_examples'].append('''
# Lambda function example
resource "aws_iam_role" "lambda_role" {
  name = "lambda-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_lambda_function" "example" {
  filename      = "lambda_function.zip"
  function_name = "example_lambda"
  role          = aws_iam_role.lambda_role.arn
  handler       = "index.handler"
  runtime       = "nodejs14.x"
}
''')
                help_data['documentation_links'].append({
                    'title': 'AWS Lambda Function Documentation',
                    'url': 'https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/lambda_function'
                })

        # Return generic help if specific category not found
        if help_data['description'] == '':
            help_data['description'] = f'Information about AWS {resource_type} resources'
            help_data['documentation_links'].append({
                'title': 'Terraform AWS Provider Documentation',
                'url': 'https://registry.terraform.io/providers/hashicorp/aws/latest/docs'
            })

        return jsonify({
            'success': True,
            'help': help_data
        })
    except Exception as e:
        logger.error(f"Error getting resource help: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# Register the blueprint with the Flask app
def init_app(app):
    app.register_blueprint(terraform_bp, url_prefix='/terraform')
    logger.info("Terraform API routes registered")

    # Make sure the workspace directory exists
    os.makedirs(WORKSPACE_DIR, exist_ok=True)
