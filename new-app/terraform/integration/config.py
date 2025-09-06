# Terraform integration configuration
import os
from flask import Blueprint

# Create blueprint
terraform_bp = Blueprint('terraform', __name__)

# Configuration
WORKSPACE_DIR = os.environ.get('TERRAFORM_WORKSPACE_DIR', os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'data', 'terraform_workspaces'))

# Import views to register routes
from . import aws_sandbox_api
