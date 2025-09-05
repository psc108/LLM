from flask import Blueprint, request, jsonify

api_bp = Blueprint('api', __name__)

@api_bp.route('/analyze-terraform', methods=['POST'])
def analyze_terraform():
    """Analyze Terraform configuration and provide feedback"""
    try:
        data = request.get_json()
        if not data or 'config' not in data:
            return jsonify({
                'success': False,
                'error': 'No configuration provided'
            })

        config = data['config']

        # Basic analysis for demo purposes
        # In a real app, you would use a proper Terraform parser/analyzer
        results = []

        # Check for AWS provider
        if 'provider "aws"' in config:
            # Check for region
            if 'region =' not in config:
                results.append({
                    'severity': 'warning',
                    'title': 'Missing AWS Region',
                    'description': 'AWS provider is defined but no region is specified.',
                    'recommendation': 'Add a region parameter to the AWS provider block.'
                })

        # Check for EC2 instances
        if 'aws_instance' in config:
            # Check for tags
            if 'aws_instance' in config and 'tags =' not in config:
                results.append({
                    'severity': 'warning',
                    'title': 'Missing Resource Tags',
                    'description': 'EC2 instances should have tags for better resource management.',
                    'recommendation': 'Add tags to your EC2 instances including at minimum: Name, Environment, and Owner.'
                })

            # Check for instance type
            if 'instance_type = "t2.micro"' in config:
                results.append({
                    'severity': 'info',
                    'title': 'Consider Instance Type',
                    'description': 'You are using t2.micro which is suitable for development but may not be ideal for production workloads.',
                    'recommendation': 'For production, consider instance types with dedicated CPU (e.g., c5, m5) based on your workload requirements.'
                })

        # Add a sample security recommendation
        results.append({
            'severity': 'error',
            'title': 'Security Group Check',
            'description': 'Unable to verify security group rules. Ensure you have not allowed unrestricted access (0.0.0.0/0) to sensitive ports.',
            'recommendation': 'Restrict access to specific IP ranges or security groups for ports 22 (SSH), 3389 (RDP), and database ports.'
        })

        return jsonify({
            'success': True,
            'results': results
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })
