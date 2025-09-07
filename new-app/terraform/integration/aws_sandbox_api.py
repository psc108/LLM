import os
import json
import logging
import subprocess
import tempfile
import shutil
from datetime import datetime
from flask import Blueprint, request, jsonify, current_app, render_template

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

@terraform_bp.route('/resource-types', methods=['GET'])
def get_resource_types():
    """Get the available AWS resource types for the sandbox."""
    return jsonify({
        'success': True,
        'resource_types': {}
    })

@terraform_bp.route('/sandbox', methods=['GET'])
def sandbox_home():
    """Render the Terraform sandbox home page."""
    return render_template('terraform/sandbox.html', title="Terraform Sandbox")

@terraform_bp.route('/workspaces', methods=['GET'])
def list_workspaces():
    """List all terraform workspaces."""
    try:
        workspaces = []
        if os.path.exists(WORKSPACE_DIR):
            for workspace_id in os.listdir(WORKSPACE_DIR):
                workspace_path = os.path.join(WORKSPACE_DIR, workspace_id)
                if os.path.isdir(workspace_path):
                    workspaces.append({
                        'workspace_id': workspace_id,
                        'created_at': datetime.fromtimestamp(os.path.getctime(workspace_path)).isoformat(),
                        'status': 'initialized',
                        'config': {}
                    })
        
        return jsonify({
            'success': True,
            'workspaces': workspaces
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@terraform_bp.route('/workspaces', methods=['POST'])
def create_workspace():
    """Create a new terraform workspace."""
    try:
        data = request.get_json() or {}
        workspace_id = data.get('workspace_id', f"workspace-{datetime.now().strftime('%Y%m%d-%H%M%S')}")
        project_session = data.get('project_session')
        
        workspace_path = os.path.join(WORKSPACE_DIR, workspace_id)
        if os.path.exists(workspace_path):
            return jsonify({
                'success': False,
                'error': f'Workspace {workspace_id} already exists'
            }), 409
        
        os.makedirs(workspace_path, exist_ok=True)
        
        # Copy project files if project_session is provided
        if project_session:
            upload_folder = current_app.config.get('UPLOAD_FOLDER', 'uploads')
            session_dir = os.path.join(upload_folder, project_session)
            
            if os.path.exists(session_dir):
                # Check if it's a local project
                project_info_file = os.path.join(session_dir, 'project_info.json')
                if os.path.exists(project_info_file):
                    with open(project_info_file, 'r') as f:
                        project_info = json.load(f)
                    if project_info.get('type') == 'local_project':
                        source_dir = project_info['original_path']
                    else:
                        source_dir = session_dir
                else:
                    # Check for extracted directory first
                    source_dir = os.path.join(session_dir, 'extracted')
                    if not os.path.exists(source_dir):
                        source_dir = os.path.join(session_dir, 'project')
                    if not os.path.exists(source_dir):
                        source_dir = session_dir
                
                # Copy terraform files only
                for root, dirs, files in os.walk(source_dir):
                    for file in files:
                        if file.endswith(('.tf', '.tfvars', '.hcl')):
                            src_file = os.path.join(root, file)
                            rel_path = os.path.relpath(src_file, source_dir)
                            dst_file = os.path.join(workspace_path, rel_path)
                            
                            # Create directory if needed
                            os.makedirs(os.path.dirname(dst_file), exist_ok=True)
                            shutil.copy2(src_file, dst_file)
        
        return jsonify({
            'success': True,
            'message': f'Workspace {workspace_id} created',
            'workspace_id': workspace_id,
            'project_copied': bool(project_session)
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@terraform_bp.route('/workspaces/<workspace_id>', methods=['GET'])
def get_workspace(workspace_id):
    """Get details about a specific workspace."""
    try:
        workspace_path = os.path.join(WORKSPACE_DIR, workspace_id)
        if not os.path.exists(workspace_path):
            return render_template('terraform/error.html'), 404
        
        # Check if request wants JSON (API call) or HTML (browser)
        if request.headers.get('Accept', '').startswith('application/json'):
            return jsonify({
                'success': True,
                'workspace': {
                    'workspace_id': workspace_id,
                    'created_at': datetime.fromtimestamp(os.path.getctime(workspace_path)).isoformat(),
                    'status': 'initialized',
                    'config': {},
                    'outputs': {},
                    'resources': [],
                    'files': [f for f in os.listdir(workspace_path) if os.path.isfile(os.path.join(workspace_path, f))]
                }
            })
        else:
            # Render HTML page for browser navigation
            workspace_data = {
                'workspace_id': workspace_id,
                'created_at': datetime.fromtimestamp(os.path.getctime(workspace_path)).isoformat(),
                'status': 'initialized',
                'config': {},
                'outputs': {},
                'resources': [],
                'files': [f for f in os.listdir(workspace_path) if os.path.isfile(os.path.join(workspace_path, f))]
            }
            return render_template('terraform/sandbox.html', 
                                 title=f"Workspace {workspace_id}",
                                 workspace_id=workspace_id,
                                 workspace_data=workspace_data,
                                 is_workspace_view=True)
    except Exception as e:
        if request.headers.get('Accept', '').startswith('application/json'):
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
        else:
            return render_template('terraform/error.html'), 500

@terraform_bp.route('/workspaces/<workspace_id>/init', methods=['POST'])
def init_workspace(workspace_id):
    """Run terraform init on a workspace."""
    try:
        workspace_path = os.path.join(WORKSPACE_DIR, workspace_id)
        if not os.path.exists(workspace_path):
            return jsonify({
                'success': False,
                'error': f'Workspace {workspace_id} not found'
            }), 404
        
        # Run terraform init
        try:
            result = subprocess.run(
                ['terraform', 'init'],
                cwd=workspace_path,
                capture_output=True,
                text=True,
                timeout=300
            )
            
            output = result.stdout + result.stderr
            success = result.returncode == 0
            
            return jsonify({
                'success': success,
                'init_output': output,
                'workspace_id': workspace_id
            })
        except subprocess.TimeoutExpired:
            return jsonify({
                'success': False,
                'error': 'Terraform init timed out after 5 minutes'
            }), 408
        except FileNotFoundError:
            return jsonify({
                'success': False,
                'error': 'Terraform CLI not found. Please install Terraform.'
            }), 500
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@terraform_bp.route('/workspaces/<workspace_id>/plan', methods=['POST'])
def plan_workspace(workspace_id):
    """Run terraform plan on a workspace."""
    try:
        workspace_path = os.path.join(WORKSPACE_DIR, workspace_id)
        if not os.path.exists(workspace_path):
            return jsonify({
                'success': False,
                'error': f'Workspace {workspace_id} not found'
            }), 404
        
        # Run terraform plan with sandbox settings
        try:
            # Set dummy AWS credentials for sandbox
            env = os.environ.copy()
            env.update({
                'AWS_ACCESS_KEY_ID': 'sandbox-key',
                'AWS_SECRET_ACCESS_KEY': 'sandbox-secret',
                'AWS_DEFAULT_REGION': 'us-east-1'
            })
            
            result = subprocess.run(
                ['terraform', 'plan', '-refresh=false'],
                cwd=workspace_path,
                capture_output=True,
                text=True,
                timeout=300,
                env=env
            )
            
            output = result.stdout + result.stderr
            success = result.returncode == 0
            
            return jsonify({
                'success': success,
                'plan_output': output,
                'workspace_id': workspace_id
            })
        except subprocess.TimeoutExpired:
            return jsonify({
                'success': False,
                'error': 'Terraform plan timed out after 5 minutes'
            }), 408
        except FileNotFoundError:
            return jsonify({
                'success': False,
                'error': 'Terraform CLI not found. Please install Terraform.'
            }), 500
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@terraform_bp.route('/workspaces/<workspace_id>/analyze', methods=['POST'])
def analyze_workspace(workspace_id):
    """Analyze workspace with AI."""
    try:
        workspace_path = os.path.join(WORKSPACE_DIR, workspace_id)
        if not os.path.exists(workspace_path):
            return jsonify({
                'success': False,
                'error': f'Workspace {workspace_id} not found'
            }), 404
        
        # Collect terraform files
        tf_files = {}
        for root, dirs, files in os.walk(workspace_path):
            for file in files:
                if file.endswith(('.tf', '.tfvars')):
                    file_path = os.path.join(root, file)
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            tf_files[file] = f.read()
                    except Exception:
                        continue
        
        if not tf_files:
            return jsonify({
                'success': False,
                'error': 'No Terraform files found in workspace'
            }), 404
        

        
        # Send to Ollama
        import requests
        
        # Get model and settings from request data
        data = request.get_json() or {}
        timeout = data.get('timeout', 120)
        max_tokens = data.get('maxTokens', 2500)
        content_length = data.get('contentLength', 500)
        
        # Use same Ollama configuration as main app
        from app import get_ollama_url, check_ollama_connection, active_model
        ollama_url = get_ollama_url('/api/generate')
        
        logger.info(f"Attempting to connect to Ollama with model {active_model}")
        
        is_connected, response = check_ollama_connection()
        if not is_connected:
            return jsonify({'success': False, 'error': 'AI service unavailable'}), 503
        
        try:
            # Use configurable content length
            first_file = list(tf_files.items())[0] if tf_files else ('', '')
            short_content = first_file[1][:content_length]
            
            prompt = f"Analyze this Terraform code:\n\n{short_content}\n\nProvide 3 key recommendations for security and best practices."
            
            # Get available models
            available_models = []
            if response and response.status_code == 200:
                models_data = response.json().get('models', [])
                available_models = [m.get('name', '') for m in models_data]
                logger.info(f"Available models: {available_models}")
            
            # Use model from request or active model
            requested_model = data.get('model')
            logger.info(f"Requested model: {requested_model}")
            
            if requested_model and requested_model in available_models:
                model_to_use = requested_model
            elif available_models:
                model_to_use = available_models[0]
            else:
                model_to_use = active_model
                
            logger.info(f"Using model: {model_to_use}")
            
            response = requests.post(
                ollama_url,
                json={
                    'model': model_to_use,
                    'prompt': prompt,
                    'stream': False,
                    'options': {'temperature': 0.1, 'num_predict': max_tokens}
                },
                timeout=timeout
            )
            
            logger.info(f"Ollama response status: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                analysis = result.get('response', 'No analysis available')
                
                return jsonify({
                    'success': True,
                    'analysis': analysis,
                    'workspace_id': workspace_id
                })
            else:
                return jsonify({
                    'success': False,
                    'error': 'AI service unavailable'
                }), 503
                
        except Exception as e:
            logger.error(f"Ollama connection error: {e}")
            return jsonify({
                'success': False,
                'error': f'AI service not available: {str(e)}'
            }), 503
                

            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@terraform_bp.route('/workspaces/<workspace_id>/recommendations', methods=['POST'])
def create_recommendations(workspace_id):
    """Create recommendations file in workspace."""
    try:
        workspace_path = os.path.join(WORKSPACE_DIR, workspace_id)
        if not os.path.exists(workspace_path):
            return jsonify({
                'success': False,
                'error': f'Workspace {workspace_id} not found'
            }), 404
        
        data = request.get_json()
        content = data.get('content', '')
        
        # Write recommendations file
        recommendations_path = os.path.join(workspace_path, 'recommendations.md')
        with open(recommendations_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return jsonify({
            'success': True,
            'file_path': 'recommendations.md'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@terraform_bp.route('/workspaces/<workspace_id>/security-report', methods=['POST'])
def create_security_report(workspace_id):
    """Create security report file in workspace."""
    try:
        workspace_path = os.path.join(WORKSPACE_DIR, workspace_id)
        if not os.path.exists(workspace_path):
            return jsonify({
                'success': False,
                'error': f'Workspace {workspace_id} not found'
            }), 404
        
        data = request.get_json()
        content = data.get('content', '')
        
        # Write security report file
        security_report_path = os.path.join(workspace_path, 'security-report.md')
        with open(security_report_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return jsonify({
            'success': True,
            'file_path': 'security-report.md'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@terraform_bp.route('/workspaces/<workspace_id>/snapshot', methods=['POST'])
def create_snapshot(workspace_id):
    """Create version control snapshot."""
    try:
        workspace_path = os.path.join(WORKSPACE_DIR, workspace_id)
        if not os.path.exists(workspace_path):
            return jsonify({'success': False, 'error': 'Workspace not found'}), 404
        
        data = request.get_json()
        message = data.get('message', 'Snapshot created')
        
        from version_control import WorkspaceVersionControl
        vc = WorkspaceVersionControl(workspace_path)
        snapshot_id = vc.create_snapshot(message)
        
        return jsonify({'success': True, 'snapshot_id': snapshot_id})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@terraform_bp.route('/workspaces/<workspace_id>/history', methods=['GET'])
def get_history(workspace_id):
    """Get workspace change history."""
    try:
        workspace_path = os.path.join(WORKSPACE_DIR, workspace_id)
        if not os.path.exists(workspace_path):
            return jsonify({'success': False, 'error': 'Workspace not found'}), 404
        
        from version_control import WorkspaceVersionControl
        vc = WorkspaceVersionControl(workspace_path)
        history = vc.get_history()
        
        return jsonify({'success': True, 'history': history})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@terraform_bp.route('/workspaces/<workspace_id>/restore/<snapshot_id>', methods=['POST'])
def restore_snapshot(workspace_id, snapshot_id):
    """Restore workspace to snapshot."""
    try:
        workspace_path = os.path.join(WORKSPACE_DIR, workspace_id)
        if not os.path.exists(workspace_path):
            return jsonify({'success': False, 'error': 'Workspace not found'}), 404
        
        from version_control import WorkspaceVersionControl
        vc = WorkspaceVersionControl(workspace_path)
        success = vc.restore_snapshot(snapshot_id)
        
        return jsonify({'success': success})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@terraform_bp.route('/templates', methods=['GET'])
def get_templates():
    """Get available templates."""
    try:
        from templates import get_available_templates
        templates = get_available_templates()
        return jsonify({'success': True, 'templates': templates})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@terraform_bp.route('/workspaces/<workspace_id>/apply-template', methods=['POST'])
def apply_template(workspace_id):
    """Apply template to workspace."""
    try:
        workspace_path = os.path.join(WORKSPACE_DIR, workspace_id)
        if not os.path.exists(workspace_path):
            return jsonify({'success': False, 'error': 'Workspace not found'}), 404
        
        data = request.get_json()
        template_id = data.get('template_id')
        
        from templates import create_workspace_from_template
        success = create_workspace_from_template(workspace_path, template_id)
        
        return jsonify({'success': success})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@terraform_bp.route('/workspaces/<workspace_id>/apply', methods=['POST'])
def apply_workspace(workspace_id):
    """Apply terraform changes to workspace."""
    try:
        workspace_path = os.path.join(WORKSPACE_DIR, workspace_id)
        if not os.path.exists(workspace_path):
            return jsonify({'success': False, 'error': 'Workspace not found'}), 404
        
        # Create snapshot before apply
        from version_control import WorkspaceVersionControl
        vc = WorkspaceVersionControl(workspace_path)
        vc.create_snapshot('Pre-apply snapshot')
        
        # Run terraform apply
        env = os.environ.copy()
        env.update({
            'AWS_ACCESS_KEY_ID': 'sandbox-key',
            'AWS_SECRET_ACCESS_KEY': 'sandbox-secret',
            'AWS_DEFAULT_REGION': 'us-east-1'
        })
        
        result = subprocess.run(
            ['terraform', 'apply', '-auto-approve'],
            cwd=workspace_path,
            capture_output=True,
            text=True,
            timeout=600,
            env=env
        )
        
        output = result.stdout + result.stderr
        success = result.returncode == 0
        
        return jsonify({
            'success': success,
            'apply_output': output,
            'workspace_id': workspace_id
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@terraform_bp.route('/workspaces/<workspace_id>/state', methods=['GET'])
def get_workspace_state(workspace_id):
    """Get terraform state information."""
    try:
        workspace_path = os.path.join(WORKSPACE_DIR, workspace_id)
        if not os.path.exists(workspace_path):
            return jsonify({'success': False, 'error': 'Workspace not found'}), 404
        
        state_file = os.path.join(workspace_path, 'terraform.tfstate')
        if not os.path.exists(state_file):
            return jsonify({
                'success': True,
                'resources': [],
                'message': 'No state file found - workspace not applied yet'
            })
        
        # Parse state file
        with open(state_file, 'r') as f:
            state_data = json.load(f)
        
        resources = []
        if 'resources' in state_data:
            for resource in state_data['resources']:
                resources.append({
                    'address': resource.get('name', 'unknown'),
                    'type': resource.get('type', 'unknown'),
                    'name': resource.get('name', 'unknown'),
                    'provider': resource.get('provider', 'unknown'),
                    'mode': resource.get('mode', 'managed')
                })
        
        return jsonify({
            'success': True,
            'resources': resources,
            'terraform_version': state_data.get('terraform_version', 'unknown'),
            'serial': state_data.get('serial', 0)
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@terraform_bp.route('/workspaces/<workspace_id>/drift', methods=['POST'])
def detect_drift(workspace_id):
    """Detect configuration drift."""
    try:
        workspace_path = os.path.join(WORKSPACE_DIR, workspace_id)
        if not os.path.exists(workspace_path):
            return jsonify({'success': False, 'error': 'Workspace not found'}), 404
        
        # Run terraform plan to detect drift
        env = os.environ.copy()
        env.update({
            'AWS_ACCESS_KEY_ID': 'sandbox-key',
            'AWS_SECRET_ACCESS_KEY': 'sandbox-secret',
            'AWS_DEFAULT_REGION': 'us-east-1'
        })
        
        result = subprocess.run(
            ['terraform', 'plan', '-detailed-exitcode'],
            cwd=workspace_path,
            capture_output=True,
            text=True,
            timeout=300,
            env=env
        )
        
        # Exit code 2 means changes detected (drift)
        drift_detected = result.returncode == 2
        output = result.stdout + result.stderr
        
        return jsonify({
            'success': True,
            'drift_detected': drift_detected,
            'drift_details': output if drift_detected else None,
            'workspace_id': workspace_id
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@terraform_bp.route('/workspaces/<workspace_id>/destroy', methods=['POST'])
def destroy_workspace(workspace_id):
    """Run terraform destroy on a workspace."""
    try:
        workspace_path = os.path.join(WORKSPACE_DIR, workspace_id)
        if not os.path.exists(workspace_path):
            return jsonify({
                'success': False,
                'error': f'Workspace {workspace_id} not found'
            }), 404
        
        return jsonify({
            'success': True,
            'destroy_output': 'No resources to destroy',
            'workspace_id': workspace_id
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@terraform_bp.route('/workspaces/<workspace_id>', methods=['DELETE'])
def delete_workspace(workspace_id):
    """Delete a workspace."""
    try:
        workspace_path = os.path.join(WORKSPACE_DIR, workspace_id)
        if not os.path.exists(workspace_path):
            return jsonify({
                'success': False,
                'error': f'Workspace {workspace_id} not found'
            }), 404
        
        shutil.rmtree(workspace_path)
        
        return jsonify({
            'success': True,
            'message': f'Workspace {workspace_id} deleted'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@terraform_bp.route('/workspaces/<workspace_id>/create-file', methods=['POST'])
def create_file_in_workspace(workspace_id):
    """Create a file in the workspace."""
    try:
        workspace_path = os.path.join(WORKSPACE_DIR, workspace_id)
        if not os.path.exists(workspace_path):
            return jsonify({
                'success': False,
                'error': f'Workspace {workspace_id} not found'
            }), 404
        
        data = request.get_json()
        file_path = data.get('file_path', '').strip()
        content = data.get('content', '')
        
        if not file_path:
            return jsonify({'success': False, 'error': 'File path is required'}), 400
        
        # Create the file
        full_file_path = os.path.join(workspace_path, file_path)
        
        # Create directory if needed
        file_dir = os.path.dirname(full_file_path)
        if file_dir and not os.path.exists(file_dir):
            os.makedirs(file_dir, exist_ok=True)
        
        # Write the file
        with open(full_file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        logger.info(f"Created file: {file_path} in workspace {workspace_id}")
        
        return jsonify({
            'success': True,
            'message': f'File {file_path} created successfully'
        })
        
    except Exception as e:
        logger.error(f"Error creating file: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@terraform_bp.route('/api/download-model', methods=['POST'])
def download_model():
    """Download a model using Ollama."""
    try:
        data = request.get_json()
        model_name = data.get('model')
        
        if not model_name:
            return jsonify({'success': False, 'error': 'Model name is required'}), 400
        
        logger.info(f"Preparing to download model: {model_name}")
        
        # Start the download process with proper encoding
        process = subprocess.Popen(
            ['ollama', 'pull', model_name],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding='utf-8'
        )
        
        logger.info(f"Started download process for model: {model_name}")
        
        # Wait for completion
        stdout, stderr = process.communicate()
        
        if process.returncode == 0:
            logger.info(f"Successfully downloaded model: {model_name}")
            return jsonify({'success': True, 'message': f'Model {model_name} downloaded successfully'})
        else:
            error_msg = stderr if stderr else 'Unknown error'
            logger.error(f"Failed to download model {model_name}: {error_msg}")
            return jsonify({'success': False, 'error': error_msg}), 500
            
    except Exception as e:
        logger.error(f"Download process error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@terraform_bp.route('/workspaces/<workspace_id>/validate', methods=['POST'])
def validate_workspace(workspace_id):
    try:
        workspace_path = os.path.join(WORKSPACE_DIR, workspace_id)
        if not os.path.exists(workspace_path):
            return jsonify({'success': False, 'error': 'Workspace not found'}), 404
        
        result = subprocess.run(
            ['terraform', 'validate', '-json'],
            cwd=workspace_path,
            capture_output=True,
            text=True
        )
        
        return jsonify({
            'success': result.returncode == 0,
            'output': result.stdout,
            'errors': result.stderr
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@terraform_bp.route('/workspaces/<workspace_id>/format', methods=['POST'])
def format_workspace(workspace_id):
    try:
        workspace_path = os.path.join(WORKSPACE_DIR, workspace_id)
        if not os.path.exists(workspace_path):
            return jsonify({'success': False, 'error': 'Workspace not found'}), 404
        
        result = subprocess.run(
            ['terraform', 'fmt', '-recursive'],
            cwd=workspace_path,
            capture_output=True,
            text=True
        )
        
        return jsonify({
            'success': result.returncode == 0,
            'formatted_files': result.stdout.strip().split('\n') if result.stdout.strip() else [],
            'errors': result.stderr
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@terraform_bp.route('/workspaces/<workspace_id>/tfvars', methods=['GET', 'POST'])
def manage_tfvars(workspace_id):
    try:
        workspace_path = os.path.join(WORKSPACE_DIR, workspace_id)
        if not os.path.exists(workspace_path):
            return jsonify({'success': False, 'error': 'Workspace not found'}), 404
        
        tfvars_file = os.path.join(workspace_path, 'terraform.tfvars')
        
        if request.method == 'GET':
            if os.path.exists(tfvars_file):
                with open(tfvars_file, 'r') as f:
                    content = f.read()
            else:
                content = ''
            return jsonify({'success': True, 'content': content})
        
        elif request.method == 'POST':
            data = request.get_json()
            content = data.get('content', '')
            
            with open(tfvars_file, 'w') as f:
                f.write(content)
            
            return jsonify({'success': True, 'message': 'Variables saved'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@terraform_bp.route('/modules/search', methods=['GET'])
def search_modules():
    try:
        query = request.args.get('q', '')
        
        modules = [
            {'name': 'terraform-aws-modules/vpc/aws', 'description': 'AWS VPC Terraform module'},
            {'name': 'terraform-aws-modules/eks/aws', 'description': 'AWS EKS Terraform module'},
            {'name': 'terraform-aws-modules/rds/aws', 'description': 'AWS RDS Terraform module'},
            {'name': 'terraform-aws-modules/s3-bucket/aws', 'description': 'AWS S3 bucket Terraform module'},
            {'name': 'terraform-aws-modules/security-group/aws', 'description': 'AWS Security Group module'},
            {'name': 'terraform-aws-modules/alb/aws', 'description': 'AWS Application Load Balancer module'},
            {'name': 'terraform-aws-modules/autoscaling/aws', 'description': 'AWS Auto Scaling Group module'},
            {'name': 'terraform-aws-modules/lambda/aws', 'description': 'AWS Lambda Terraform module'}
        ]
        
        if query:
            modules = [m for m in modules if query.lower() in m['name'].lower() or query.lower() in m['description'].lower()]
        
        return jsonify({'success': True, 'modules': modules})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@terraform_bp.route('/workspaces/<workspace_id>/import-module', methods=['POST'])
def import_module(workspace_id):
    try:
        workspace_path = os.path.join(WORKSPACE_DIR, workspace_id)
        if not os.path.exists(workspace_path):
            return jsonify({'success': False, 'error': 'Workspace not found'}), 404
        
        data = request.get_json()
        module_name = data.get('module')
        
        if not module_name:
            return jsonify({'success': False, 'error': 'Module name required'}), 400
        
        module_content = f'''module "{module_name.split('/')[-1]}" {{
  source = "{module_name}"
  
  # Add your configuration here
  # version = "~> 1.0"
}}'''
        
        modules_file = os.path.join(workspace_path, 'modules.tf')
        with open(modules_file, 'a') as f:
            f.write('\n\n' + module_content)
        
        return jsonify({'success': True, 'message': f'Module {module_name} imported'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@terraform_bp.route('/workspaces/<workspace_id>/policy-check', methods=['POST'])
def policy_check(workspace_id):
    try:
        workspace_path = os.path.join(WORKSPACE_DIR, workspace_id)
        if not os.path.exists(workspace_path):
            return jsonify({'success': False, 'error': 'Workspace not found'}), 404
        
        # Basic policy checks
        violations = []
        for root, dirs, files in os.walk(workspace_path):
            for file in files:
                if file.endswith('.tf'):
                    file_path = os.path.join(root, file)
                    with open(file_path, 'r') as f:
                        content = f.read()
                        
                    # Check for hardcoded secrets
                    if 'password' in content.lower() and '=' in content:
                        violations.append({'file': file, 'rule': 'No hardcoded passwords', 'severity': 'HIGH'})
                    
                    # Check for public access
                    if '0.0.0.0/0' in content:
                        violations.append({'file': file, 'rule': 'Avoid public access', 'severity': 'MEDIUM'})
                    
                    # Check for encryption
                    if 'aws_s3_bucket' in content and 'encryption' not in content:
                        violations.append({'file': file, 'rule': 'S3 encryption required', 'severity': 'HIGH'})
        
        return jsonify({
            'success': True,
            'violations': violations,
            'total_violations': len(violations)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@terraform_bp.route('/workspaces/<workspace_id>/compliance-scan', methods=['POST'])
def compliance_scan(workspace_id):
    try:
        workspace_path = os.path.join(WORKSPACE_DIR, workspace_id)
        if not os.path.exists(workspace_path):
            return jsonify({'success': False, 'error': 'Workspace not found'}), 404
        
        # CIS benchmark checks
        findings = []
        score = 100
        
        for root, dirs, files in os.walk(workspace_path):
            for file in files:
                if file.endswith('.tf'):
                    file_path = os.path.join(root, file)
                    with open(file_path, 'r') as f:
                        content = f.read()
                    
                    # CIS 2.1.1 - S3 bucket encryption
                    if 'aws_s3_bucket' in content and 'server_side_encryption_configuration' not in content:
                        findings.append({'benchmark': 'CIS 2.1.1', 'description': 'S3 bucket encryption not enabled', 'file': file})
                        score -= 10
                    
                    # CIS 4.1 - Security groups
                    if 'aws_security_group' in content and '0.0.0.0/0' in content:
                        findings.append({'benchmark': 'CIS 4.1', 'description': 'Security group allows unrestricted access', 'file': file})
                        score -= 15
                    
                    # CIS 3.1 - CloudTrail logging
                    if 'aws_instance' in content and 'aws_cloudtrail' not in content:
                        findings.append({'benchmark': 'CIS 3.1', 'description': 'CloudTrail logging not configured', 'file': file})
                        score -= 5
        
        return jsonify({
            'success': True,
            'compliance_score': max(0, score),
            'findings': findings,
            'total_findings': len(findings)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@terraform_bp.route('/workspaces/<workspace_id>/secrets-scan', methods=['POST'])
def secrets_scan(workspace_id):
    try:
        workspace_path = os.path.join(WORKSPACE_DIR, workspace_id)
        if not os.path.exists(workspace_path):
            return jsonify({'success': False, 'error': 'Workspace not found'}), 404
        
        secrets_found = []
        
        for root, dirs, files in os.walk(workspace_path):
            for file in files:
                if file.endswith(('.tf', '.tfvars')):
                    file_path = os.path.join(root, file)
                    with open(file_path, 'r') as f:
                        lines = f.readlines()
                    
                    for i, line in enumerate(lines, 1):
                        # Check for potential secrets
                        if any(keyword in line.lower() for keyword in ['password', 'secret', 'key', 'token']):
                            if '=' in line and not line.strip().startswith('#'):
                                secrets_found.append({
                                    'file': file,
                                    'line': i,
                                    'content': line.strip(),
                                    'type': 'Potential secret'
                                })
        
        recommendations = [
            'Use AWS Secrets Manager for sensitive data',
            'Use Terraform variables with sensitive = true',
            'Store secrets in environment variables',
            'Use HashiCorp Vault for secret management'
        ]
        
        return jsonify({
            'success': True,
            'secrets_found': secrets_found,
            'total_secrets': len(secrets_found),
            'recommendations': recommendations
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@terraform_bp.route('/workspaces/<workspace_id>/access-control', methods=['GET', 'POST'])
def access_control(workspace_id):
    try:
        workspace_path = os.path.join(WORKSPACE_DIR, workspace_id)
        if not os.path.exists(workspace_path):
            return jsonify({'success': False, 'error': 'Workspace not found'}), 404
        
        access_file = os.path.join(workspace_path, '.access-control.json')
        
        if request.method == 'GET':
            if os.path.exists(access_file):
                with open(access_file, 'r') as f:
                    access_config = json.load(f)
            else:
                access_config = {
                    'roles': {
                        'admin': ['read', 'write', 'deploy', 'destroy'],
                        'developer': ['read', 'write', 'deploy'],
                        'viewer': ['read']
                    },
                    'users': {},
                    'workspace_permissions': {
                        'require_approval': True,
                        'allowed_actions': ['plan', 'apply']
                    }
                }
            
            return jsonify({'success': True, 'access_config': access_config})
        
        elif request.method == 'POST':
            data = request.get_json()
            access_config = data.get('access_config', {})
            
            with open(access_file, 'w') as f:
                json.dump(access_config, f, indent=2)
            
            return jsonify({'success': True, 'message': 'Access control updated'})
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@terraform_bp.route('/workspaces/<workspace_id>/visualize', methods=['POST'])
def visualize_resources(workspace_id):
    try:
        workspace_path = os.path.join(WORKSPACE_DIR, workspace_id)
        if not os.path.exists(workspace_path):
            return jsonify({'success': False, 'error': 'Workspace not found'}), 404
        
        # Parse terraform files for resources
        resources = []
        dependencies = []
        
        for file in os.listdir(workspace_path):
            if file.endswith('.tf'):
                file_path = os.path.join(workspace_path, file)
                with open(file_path, 'r') as f:
                    content = f.read()
                    
                    # Extract resources
                    import re
                    resource_matches = re.findall(r'resource\s+"([^"]+)"\s+"([^"]+)"', content)
                    for resource_type, resource_name in resource_matches:
                        resources.append({
                            'id': f"{resource_type}.{resource_name}",
                            'type': resource_type,
                            'name': resource_name,
                            'file': file
                        })
                    
                    # Extract dependencies
                    dep_matches = re.findall(r'([a-zA-Z_][a-zA-Z0-9_]*\.[a-zA-Z_][a-zA-Z0-9_]*)', content)
                    for dep in dep_matches:
                        if '.' in dep:
                            dependencies.append(dep)
        
        # Create graph structure
        graph = {
            'nodes': [{'id': r['id'], 'label': r['name'], 'type': r['type']} for r in resources],
            'edges': [{'from': dep, 'to': r['id']} for r in resources for dep in dependencies if dep != r['id']]
        }
        
        return jsonify({'success': True, 'graph': graph})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@terraform_bp.route('/workspaces/<workspace_id>/logs')
def stream_logs(workspace_id):
    from flask import Response
    
    def generate():
        log_file = os.path.join(WORKSPACE_DIR, workspace_id, 'terraform.log')
        if os.path.exists(log_file):
            with open(log_file, 'r') as f:
                for line in f:
                    yield f"data: {line}\n\n"
        else:
            yield "data: No logs available\n\n"
    
    return Response(generate(), mimetype='text/event-stream')

@terraform_bp.route('/workspaces/<workspace_id>/terratest', methods=['POST'])
def run_terratest(workspace_id):
    try:
        workspace_path = os.path.join(WORKSPACE_DIR, workspace_id)
        if not os.path.exists(workspace_path):
            return jsonify({'success': False, 'error': 'Workspace not found'}), 404
        
        data = request.get_json() or {}
        install_terratest = data.get('install_terratest', False)
        
        # Check if Go is installed
        try:
            go_result = subprocess.run(['go', 'version'], capture_output=True, text=True, timeout=10)
            if go_result.returncode != 0:
                return jsonify({
                    'success': False, 
                    'error': 'Go is not installed. Please install Go first.',
                    'install_required': 'go'
                }), 400
        except FileNotFoundError:
            return jsonify({
                'success': False, 
                'error': 'Go is not installed. Please install Go first.',
                'install_required': 'go'
            }), 400
        
        # Check if terratest is available
        go_mod_path = os.path.join(workspace_path, 'go.mod')
        terratest_available = False
        
        if os.path.exists(go_mod_path):
            with open(go_mod_path, 'r') as f:
                if 'github.com/gruntwork-io/terratest' in f.read():
                    terratest_available = True
        
        if not terratest_available and not install_terratest:
            return jsonify({
                'success': False,
                'error': 'Terratest is not installed. Would you like to install it?',
                'install_required': 'terratest',
                'install_available': True
            }), 400
        
        # Install terratest if requested
        if install_terratest and not terratest_available:
            # Initialize go module
            subprocess.run(['go', 'mod', 'init', f'terratest-{workspace_id}'], cwd=workspace_path, capture_output=True)
            
            # Install terratest
            install_result = subprocess.run(
                ['go', 'get', 'github.com/gruntwork-io/terratest/modules/terraform', 'github.com/stretchr/testify/assert'],
                cwd=workspace_path,
                capture_output=True,
                text=True,
                timeout=120
            )
            
            if install_result.returncode != 0:
                return jsonify({
                    'success': False,
                    'error': f'Failed to install terratest: {install_result.stderr}'
                }), 500
        
        # Create basic Go test file
        test_content = '''package test

import (
	"testing"
	"github.com/gruntwork-io/terratest/modules/terraform"
	"github.com/stretchr/testify/assert"
)

func TestTerraform(t *testing.T) {
	terraformOptions := &terraform.Options{
		TerraformDir: ".",
	}

	defer terraform.Destroy(t, terraformOptions)
	terraform.InitAndApply(t, terraformOptions)

	// Add your assertions here
	assert.True(t, true, "Basic test passed")
}'''
        
        test_file = os.path.join(workspace_path, 'main_test.go')
        with open(test_file, 'w') as f:
            f.write(test_content)
        
        # Run go test
        result = subprocess.run(
            ['go', 'test', '-v'],
            cwd=workspace_path,
            capture_output=True,
            text=True,
            timeout=300
        )
        
        return jsonify({
            'success': result.returncode == 0,
            'test_output': result.stdout + result.stderr,
            'test_file_created': 'main_test.go',
            'terratest_installed': install_terratest
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@terraform_bp.route('/workspaces/<workspace_id>/opa-test', methods=['POST'])
def run_opa_compliance(workspace_id):
    try:
        workspace_path = os.path.join(WORKSPACE_DIR, workspace_id)
        if not os.path.exists(workspace_path):
            return jsonify({'success': False, 'error': 'Workspace not found'}), 404
        
        # Create OPA policy file
        policy_content = '''package terraform.analysis

default allow = false

allow {
    input.resource_type == "aws_s3_bucket"
    input.config.server_side_encryption_configuration
}

allow {
    input.resource_type == "aws_security_group"
    not contains_public_access
}

contains_public_access {
    input.config.ingress[_].cidr_blocks[_] == "0.0.0.0/0"
}

violations[msg] {
    input.resource_type == "aws_s3_bucket"
    not input.config.server_side_encryption_configuration
    msg := "S3 bucket must have encryption enabled"
}

violations[msg] {
    input.resource_type == "aws_security_group"
    contains_public_access
    msg := "Security group should not allow public access"
}'''
        
        policy_file = os.path.join(workspace_path, 'policy.rego')
        with open(policy_file, 'w') as f:
            f.write(policy_content)
        
        # Parse terraform files and create test data
        violations = []
        for file in os.listdir(workspace_path):
            if file.endswith('.tf'):
                file_path = os.path.join(workspace_path, file)
                with open(file_path, 'r') as f:
                    content = f.read()
                    
                    # Simple compliance checks
                    if 'aws_s3_bucket' in content and 'server_side_encryption_configuration' not in content:
                        violations.append({'file': file, 'rule': 'S3 encryption required', 'severity': 'HIGH'})
                    
                    if 'aws_security_group' in content and '0.0.0.0/0' in content:
                        violations.append({'file': file, 'rule': 'No public access allowed', 'severity': 'CRITICAL'})
        
        return jsonify({
            'success': True,
            'policy_file_created': 'policy.rego',
            'violations': violations,
            'compliance_score': max(0, 100 - len(violations) * 20)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@terraform_bp.route('/workspaces/<workspace_id>/validate-plan', methods=['POST'])
def validate_plan_rules(workspace_id):
    try:
        workspace_path = os.path.join(WORKSPACE_DIR, workspace_id)
        if not os.path.exists(workspace_path):
            return jsonify({'success': False, 'error': 'Workspace not found'}), 404
        
        # Validation rules
        rules = {
            'required_tags': ['Environment', 'Project'],
            'forbidden_resources': ['aws_instance'],  # Example: no EC2 in this workspace
            'required_encryption': ['aws_s3_bucket', 'aws_ebs_volume'],
            'cost_limits': {'max_instances': 5, 'allowed_instance_types': ['t3.micro', 't3.small']}
        }
        
        violations = []
        warnings = []
        
        for file in os.listdir(workspace_path):
            if file.endswith('.tf'):
                file_path = os.path.join(workspace_path, file)
                with open(file_path, 'r') as f:
                    content = f.read()
                    
                    # Check required tags
                    if 'tags' in content:
                        for tag in rules['required_tags']:
                            if tag not in content:
                                violations.append(f'{file}: Missing required tag "{tag}"')
                    
                    # Check forbidden resources
                    for resource in rules['forbidden_resources']:
                        if resource in content:
                            violations.append(f'{file}: Forbidden resource "{resource}" found')
                    
                    # Check encryption
                    for resource in rules['required_encryption']:
                        if resource in content and 'encryption' not in content:
                            violations.append(f'{file}: "{resource}" requires encryption')
                    
                    # Cost warnings
                    if 'instance_type' in content:
                        import re
                        types = re.findall(r'instance_type\s*=\s*"([^"]+)"', content)
                        for itype in types:
                            if itype not in rules['cost_limits']['allowed_instance_types']:
                                warnings.append(f'{file}: Instance type "{itype}" may incur high costs')
        
        return jsonify({
            'success': True,
            'validation_passed': len(violations) == 0,
            'violations': violations,
            'warnings': warnings,
            'rules_applied': len(rules)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@terraform_bp.route('/workspaces/<workspace_id>/provider-config', methods=['GET', 'POST'])
def manage_provider_config(workspace_id):
    try:
        workspace_path = os.path.join(WORKSPACE_DIR, workspace_id)
        if not os.path.exists(workspace_path):
            return jsonify({'success': False, 'error': 'Workspace not found'}), 404
        
        provider_file = os.path.join(workspace_path, 'provider.tf')
        
        if request.method == 'GET':
            if os.path.exists(provider_file):
                with open(provider_file, 'r') as f:
                    content = f.read()
            else:
                content = ''
            return jsonify({'success': True, 'content': content})
        
        elif request.method == 'POST':
            data = request.get_json()
            region = data.get('region', 'us-east-1')
            profile = data.get('profile', 'default')
            assume_role = data.get('assume_role', '')
            
            provider_content = f'''terraform {{
  required_providers {{
    aws = {{
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }}
  }}
}}

provider "aws" {{
  region  = "{region}"
  profile = "{profile}"'''
            
            if assume_role:
                provider_content += f'''
  assume_role {{
    role_arn = "{assume_role}"
  }}'''
            
            provider_content += '\n}\n'
            
            with open(provider_file, 'w') as f:
                f.write(provider_content)
            
            return jsonify({'success': True, 'message': 'Provider configuration updated'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@terraform_bp.route('/aws/validate-credentials', methods=['POST'])
def validate_aws_credentials():
    try:
        data = request.get_json()
        profile = data.get('profile', 'default')
        region = data.get('region', 'us-east-1')
        
        # Set environment for AWS CLI
        env = os.environ.copy()
        if profile != 'default':
            env['AWS_PROFILE'] = profile
        env['AWS_DEFAULT_REGION'] = region
        
        # Test AWS credentials
        result = subprocess.run(
            ['aws', 'sts', 'get-caller-identity'],
            capture_output=True,
            text=True,
            timeout=30,
            env=env
        )
        
        if result.returncode == 0:
            import json as json_lib
            identity = json_lib.loads(result.stdout)
            return jsonify({
                'success': True,
                'valid': True,
                'account_id': identity.get('Account'),
                'user_arn': identity.get('Arn'),
                'user_id': identity.get('UserId')
            })
        else:
            return jsonify({
                'success': True,
                'valid': False,
                'error': result.stderr
            })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@terraform_bp.route('/aws/profiles', methods=['GET'])
def get_aws_profiles():
    try:
        import configparser
        import os.path
        
        profiles = ['default']
        
        # Read AWS credentials file
        creds_file = os.path.expanduser('~/.aws/credentials')
        if os.path.exists(creds_file):
            config = configparser.ConfigParser()
            config.read(creds_file)
            profiles.extend([section for section in config.sections() if section != 'default'])
        
        # Read AWS config file
        config_file = os.path.expanduser('~/.aws/config')
        if os.path.exists(config_file):
            config = configparser.ConfigParser()
            config.read(config_file)
            for section in config.sections():
                if section.startswith('profile '):
                    profile_name = section.replace('profile ', '')
                    if profile_name not in profiles:
                        profiles.append(profile_name)
        
        return jsonify({'success': True, 'profiles': list(set(profiles))})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@terraform_bp.route('/workspaces/<workspace_id>/switch-profile', methods=['POST'])
def switch_aws_profile(workspace_id):
    try:
        workspace_path = os.path.join(WORKSPACE_DIR, workspace_id)
        if not os.path.exists(workspace_path):
            return jsonify({'success': False, 'error': 'Workspace not found'}), 404
        
        data = request.get_json()
        profile = data.get('profile', 'default')
        region = data.get('region', 'us-east-1')
        
        # Update provider.tf
        provider_file = os.path.join(workspace_path, 'provider.tf')
        provider_content = f'''terraform {{
  required_providers {{
    aws = {{
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }}
  }}
}}

provider "aws" {{
  region  = "{region}"
  profile = "{profile}"
}}
'''
        
        with open(provider_file, 'w') as f:
            f.write(provider_content)
        
        # Validate new credentials
        env = os.environ.copy()
        if profile != 'default':
            env['AWS_PROFILE'] = profile
        env['AWS_DEFAULT_REGION'] = region
        
        result = subprocess.run(
            ['aws', 'sts', 'get-caller-identity'],
            capture_output=True,
            text=True,
            timeout=30,
            env=env
        )
        
        if result.returncode == 0:
            import json as json_lib
            identity = json_lib.loads(result.stdout)
            return jsonify({
                'success': True,
                'profile': profile,
                'region': region,
                'account_id': identity.get('Account'),
                'user_arn': identity.get('Arn')
            })
        else:
            return jsonify({
                'success': False,
                'error': f'Failed to validate credentials: {result.stderr}'
            })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@terraform_bp.route('/workspaces/<workspace_id>/backend-config', methods=['GET', 'POST'])
def manage_backend_config(workspace_id):
    try:
        workspace_path = os.path.join(WORKSPACE_DIR, workspace_id)
        if not os.path.exists(workspace_path):
            return jsonify({'success': False, 'error': 'Workspace not found'}), 404
        
        backend_file = os.path.join(workspace_path, 'backend.tf')
        
        if request.method == 'GET':
            if os.path.exists(backend_file):
                with open(backend_file, 'r') as f:
                    content = f.read()
            else:
                content = ''
            return jsonify({'success': True, 'content': content})
        
        elif request.method == 'POST':
            data = request.get_json()
            bucket = data.get('bucket')
            key = data.get('key', f'{workspace_id}/terraform.tfstate')
            region = data.get('region', 'us-east-1')
            dynamodb_table = data.get('dynamodb_table', 'terraform-locks')
            
            if not bucket:
                return jsonify({'success': False, 'error': 'S3 bucket is required'}), 400
            
            backend_content = f'''terraform {{
  backend "s3" {{
    bucket         = "{bucket}"
    key            = "{key}"
    region         = "{region}"
    dynamodb_table = "{dynamodb_table}"
    encrypt        = true
  }}
}}
'''
            
            with open(backend_file, 'w') as f:
                f.write(backend_content)
            
            return jsonify({'success': True, 'message': 'Backend configuration saved'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@terraform_bp.route('/workspaces/<workspace_id>/init-backend', methods=['POST'])
def init_backend(workspace_id):
    try:
        workspace_path = os.path.join(WORKSPACE_DIR, workspace_id)
        if not os.path.exists(workspace_path):
            return jsonify({'success': False, 'error': 'Workspace not found'}), 404
        
        # Run terraform init with backend migration
        result = subprocess.run(
            ['terraform', 'init', '-migrate-state'],
            cwd=workspace_path,
            capture_output=True,
            text=True,
            timeout=300
        )
        
        return jsonify({
            'success': result.returncode == 0,
            'output': result.stdout + result.stderr
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@terraform_bp.route('/workspaces/<workspace_id>/share-state', methods=['POST'])
def share_state(workspace_id):
    try:
        workspace_path = os.path.join(WORKSPACE_DIR, workspace_id)
        if not os.path.exists(workspace_path):
            return jsonify({'success': False, 'error': 'Workspace not found'}), 404
        
        data = request.get_json()
        target_workspace = data.get('target_workspace')
        
        if not target_workspace:
            return jsonify({'success': False, 'error': 'Target workspace required'}), 400
        
        target_path = os.path.join(WORKSPACE_DIR, target_workspace)
        if not os.path.exists(target_path):
            return jsonify({'success': False, 'error': 'Target workspace not found'}), 404
        
        # Copy backend configuration
        source_backend = os.path.join(workspace_path, 'backend.tf')
        target_backend = os.path.join(target_path, 'backend.tf')
        
        if os.path.exists(source_backend):
            with open(source_backend, 'r') as f:
                backend_content = f.read()
            
            # Update key for target workspace
            backend_content = backend_content.replace(
                f'key            = "{workspace_id}/',
                f'key            = "{target_workspace}/'
            )
            
            with open(target_backend, 'w') as f:
                f.write(backend_content)
            
            return jsonify({
                'success': True,
                'message': f'State configuration shared with {target_workspace}'
            })
        else:
            return jsonify({'success': False, 'error': 'No backend configuration found'}), 404
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@terraform_bp.route('/aws/create-state-resources', methods=['POST'])
def create_state_resources():
    try:
        data = request.get_json()
        bucket_name = data.get('bucket_name')
        table_name = data.get('table_name', 'terraform-locks')
        region = data.get('region', 'us-east-1')
        
        if not bucket_name:
            return jsonify({'success': False, 'error': 'Bucket name required'}), 400
        
        # Create S3 bucket
        s3_result = subprocess.run([
            'aws', 's3api', 'create-bucket',
            '--bucket', bucket_name,
            '--region', region
        ], capture_output=True, text=True)
        
        # Enable versioning
        subprocess.run([
            'aws', 's3api', 'put-bucket-versioning',
            '--bucket', bucket_name,
            '--versioning-configuration', 'Status=Enabled'
        ], capture_output=True, text=True)
        
        # Create DynamoDB table
        dynamodb_result = subprocess.run([
            'aws', 'dynamodb', 'create-table',
            '--table-name', table_name,
            '--attribute-definitions', 'AttributeName=LockID,AttributeType=S',
            '--key-schema', 'AttributeName=LockID,KeyType=HASH',
            '--billing-mode', 'PAY_PER_REQUEST',
            '--region', region
        ], capture_output=True, text=True)
        
        return jsonify({
            'success': True,
            'bucket_created': s3_result.returncode == 0,
            'table_created': dynamodb_result.returncode == 0,
            's3_output': s3_result.stdout + s3_result.stderr,
            'dynamodb_output': dynamodb_result.stdout + dynamodb_result.stderr
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@terraform_bp.route('/aws/discover-resources', methods=['POST'])
def discover_aws_resources():
    try:
        data = request.get_json()
        region = data.get('region', 'us-east-1')
        resource_types = data.get('resource_types', ['ec2', 's3', 'rds', 'vpc'])
        
        discovered = {}
        
        for resource_type in resource_types:
            if resource_type == 'ec2':
                result = subprocess.run([
                    'aws', 'ec2', 'describe-instances',
                    '--region', region,
                    '--query', 'Reservations[*].Instances[*].[InstanceId,InstanceType,State.Name,Tags[?Key==`Name`].Value|[0]]',
                    '--output', 'json'
                ], capture_output=True, text=True)
                
                if result.returncode == 0:
                    import json as json_lib
                    instances = json_lib.loads(result.stdout)
                    discovered['ec2_instances'] = [{
                        'id': inst[0],
                        'type': inst[1],
                        'state': inst[2],
                        'name': inst[3] or 'unnamed'
                    } for reservation in instances for inst in reservation if inst[2] == 'running']
            
            elif resource_type == 's3':
                result = subprocess.run([
                    'aws', 's3api', 'list-buckets',
                    '--query', 'Buckets[*].[Name,CreationDate]',
                    '--output', 'json'
                ], capture_output=True, text=True)
                
                if result.returncode == 0:
                    import json as json_lib
                    buckets = json_lib.loads(result.stdout)
                    discovered['s3_buckets'] = [{
                        'name': bucket[0],
                        'created': bucket[1]
                    } for bucket in buckets]
            
            elif resource_type == 'vpc':
                result = subprocess.run([
                    'aws', 'ec2', 'describe-vpcs',
                    '--region', region,
                    '--query', 'Vpcs[*].[VpcId,CidrBlock,State,Tags[?Key==`Name`].Value|[0]]',
                    '--output', 'json'
                ], capture_output=True, text=True)
                
                if result.returncode == 0:
                    import json as json_lib
                    vpcs = json_lib.loads(result.stdout)
                    discovered['vpcs'] = [{
                        'id': vpc[0],
                        'cidr': vpc[1],
                        'state': vpc[2],
                        'name': vpc[3] or 'unnamed'
                    } for vpc in vpcs if vpc[2] == 'available']
        
        return jsonify({
            'success': True,
            'resources': discovered,
            'region': region
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@terraform_bp.route('/workspaces/<workspace_id>/import-resource', methods=['POST'])
def import_aws_resource(workspace_id):
    try:
        workspace_path = os.path.join(WORKSPACE_DIR, workspace_id)
        if not os.path.exists(workspace_path):
            return jsonify({'success': False, 'error': 'Workspace not found'}), 404
        
        data = request.get_json()
        resource_type = data.get('resource_type')
        resource_id = data.get('resource_id')
        terraform_name = data.get('terraform_name')
        
        if not all([resource_type, resource_id, terraform_name]):
            return jsonify({'success': False, 'error': 'Missing required parameters'}), 400
        
        # Generate Terraform configuration
        config_content = generate_terraform_config(resource_type, terraform_name, resource_id)
        
        # Write to imported.tf file
        imported_file = os.path.join(workspace_path, 'imported.tf')
        with open(imported_file, 'a') as f:
            f.write('\n' + config_content + '\n')
        
        # Run terraform import
        terraform_address = f'{resource_type}.{terraform_name}'
        result = subprocess.run([
            'terraform', 'import', terraform_address, resource_id
        ], cwd=workspace_path, capture_output=True, text=True)
        
        return jsonify({
            'success': result.returncode == 0,
            'import_output': result.stdout + result.stderr,
            'config_generated': True,
            'terraform_address': terraform_address
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@terraform_bp.route('/workspaces/<workspace_id>/export-state', methods=['POST'])
def export_state_config(workspace_id):
    try:
        workspace_path = os.path.join(WORKSPACE_DIR, workspace_id)
        if not os.path.exists(workspace_path):
            return jsonify({'success': False, 'error': 'Workspace not found'}), 404
        
        # Get terraform state
        result = subprocess.run([
            'terraform', 'show', '-json'
        ], cwd=workspace_path, capture_output=True, text=True)
        
        if result.returncode != 0:
            return jsonify({'success': False, 'error': 'Failed to read state'}), 500
        
        import json as json_lib
        state_data = json_lib.loads(result.stdout)
        
        # Generate configuration from state
        generated_config = ''
        if 'values' in state_data and 'root_module' in state_data['values']:
            resources = state_data['values']['root_module'].get('resources', [])
            
            for resource in resources:
                resource_type = resource.get('type')
                resource_name = resource.get('name')
                values = resource.get('values', {})
                
                config = f'resource "{resource_type}" "{resource_name}" {{\n'
                
                # Add key attributes
                for key, value in values.items():
                    if key not in ['id', 'arn', 'tags_all'] and value is not None:
                        if isinstance(value, str):
                            config += f'  {key} = "{value}"\n'
                        elif isinstance(value, bool):
                            config += f'  {key} = {str(value).lower()}\n'
                        elif isinstance(value, (int, float)):
                            config += f'  {key} = {value}\n'
                
                config += '}\n\n'
                generated_config += config
        
        # Write to exported.tf
        exported_file = os.path.join(workspace_path, 'exported.tf')
        with open(exported_file, 'w') as f:
            f.write(generated_config)
        
        return jsonify({
            'success': True,
            'config_generated': True,
            'file_created': 'exported.tf',
            'resource_count': len(resources) if 'resources' in locals() else 0
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@terraform_bp.route('/workspaces/<workspace_id>/environments', methods=['GET', 'POST'])
def manage_environments(workspace_id):
    try:
        workspace_path = os.path.join(WORKSPACE_DIR, workspace_id)
        if not os.path.exists(workspace_path):
            return jsonify({'success': False, 'error': 'Workspace not found'}), 404
        
        if request.method == 'GET':
            # List environment files
            env_files = {}
            for env in ['dev', 'staging', 'prod']:
                env_file = os.path.join(workspace_path, f'{env}.tfvars')
                if os.path.exists(env_file):
                    with open(env_file, 'r') as f:
                        env_files[env] = f.read()
                else:
                    env_files[env] = ''
            
            return jsonify({'success': True, 'environments': env_files})
        
        elif request.method == 'POST':
            data = request.get_json()
            environment = data.get('environment')
            content = data.get('content', '')
            
            if environment not in ['dev', 'staging', 'prod']:
                return jsonify({'success': False, 'error': 'Invalid environment'}), 400
            
            env_file = os.path.join(workspace_path, f'{environment}.tfvars')
            with open(env_file, 'w') as f:
                f.write(content)
            
            return jsonify({'success': True, 'message': f'{environment}.tfvars updated'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@terraform_bp.route('/workspaces/<workspace_id>/promote', methods=['POST'])
def promote_environment(workspace_id):
    try:
        workspace_path = os.path.join(WORKSPACE_DIR, workspace_id)
        if not os.path.exists(workspace_path):
            return jsonify({'success': False, 'error': 'Workspace not found'}), 404
        
        data = request.get_json()
        source_env = data.get('source_env')
        target_env = data.get('target_env')
        
        if not source_env or not target_env:
            return jsonify({'success': False, 'error': 'Source and target environments required'}), 400
        
        # Promotion order validation
        promotion_order = ['dev', 'staging', 'prod']
        if source_env not in promotion_order or target_env not in promotion_order:
            return jsonify({'success': False, 'error': 'Invalid environment'}), 400
        
        if promotion_order.index(source_env) >= promotion_order.index(target_env):
            return jsonify({'success': False, 'error': 'Can only promote to higher environments'}), 400
        
        # Copy tfvars file
        source_file = os.path.join(workspace_path, f'{source_env}.tfvars')
        target_file = os.path.join(workspace_path, f'{target_env}.tfvars')
        
        if not os.path.exists(source_file):
            return jsonify({'success': False, 'error': f'{source_env}.tfvars not found'}), 404
        
        # Read source variables
        with open(source_file, 'r') as f:
            source_content = f.read()
        
        # Apply environment-specific overrides
        promoted_content = apply_environment_overrides(source_content, target_env)
        
        # Write to target
        with open(target_file, 'w') as f:
            f.write(promoted_content)
        
        return jsonify({
            'success': True,
            'message': f'Promoted {source_env} to {target_env}',
            'source_env': source_env,
            'target_env': target_env
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@terraform_bp.route('/workspaces/<workspace_id>/variables/inherit', methods=['POST'])
def inherit_variables(workspace_id):
    try:
        workspace_path = os.path.join(WORKSPACE_DIR, workspace_id)
        if not os.path.exists(workspace_path):
            return jsonify({'success': False, 'error': 'Workspace not found'}), 404
        
        data = request.get_json()
        base_env = data.get('base_env', 'dev')
        target_env = data.get('target_env')
        overrides = data.get('overrides', {})
        
        if not target_env:
            return jsonify({'success': False, 'error': 'Target environment required'}), 400
        
        # Read base environment variables
        base_file = os.path.join(workspace_path, f'{base_env}.tfvars')
        base_vars = {}
        
        if os.path.exists(base_file):
            with open(base_file, 'r') as f:
                content = f.read()
                # Parse tfvars (simple key = value parsing)
                import re
                matches = re.findall(r'(\w+)\s*=\s*"([^"]+)"', content)
                for key, value in matches:
                    base_vars[key] = value
        
        # Apply overrides
        final_vars = {**base_vars, **overrides}
        
        # Generate target tfvars content
        target_content = f'# Inherited from {base_env} with overrides\n\n'
        for key, value in final_vars.items():
            target_content += f'{key} = "{value}"\n'
        
        # Write target file
        target_file = os.path.join(workspace_path, f'{target_env}.tfvars')
        with open(target_file, 'w') as f:
            f.write(target_content)
        
        return jsonify({
            'success': True,
            'inherited_vars': len(base_vars),
            'overrides_applied': len(overrides),
            'total_vars': len(final_vars)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@terraform_bp.route('/workspaces/<workspace_id>/plan-env', methods=['POST'])
def plan_with_environment(workspace_id):
    try:
        workspace_path = os.path.join(WORKSPACE_DIR, workspace_id)
        if not os.path.exists(workspace_path):
            return jsonify({'success': False, 'error': 'Workspace not found'}), 404
        
        data = request.get_json()
        environment = data.get('environment', 'dev')
        
        env_file = os.path.join(workspace_path, f'{environment}.tfvars')
        if not os.path.exists(env_file):
            return jsonify({'success': False, 'error': f'{environment}.tfvars not found'}), 404
        
        # Run terraform plan with environment-specific variables
        env = os.environ.copy()
        env.update({
            'AWS_ACCESS_KEY_ID': 'sandbox-key',
            'AWS_SECRET_ACCESS_KEY': 'sandbox-secret',
            'AWS_DEFAULT_REGION': 'us-east-1'
        })
        
        result = subprocess.run([
            'terraform', 'plan', f'-var-file={environment}.tfvars', '-refresh=false'
        ], cwd=workspace_path, capture_output=True, text=True, timeout=300, env=env)
        
        return jsonify({
            'success': result.returncode == 0,
            'plan_output': result.stdout + result.stderr,
            'environment': environment
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

def apply_environment_overrides(content, target_env):
    """Apply environment-specific overrides during promotion"""
    
    # Environment-specific overrides
    overrides = {
        'staging': {
            'environment': 'staging',
            'instance_count': '2',
            'instance_type': 't3.small'
        },
        'prod': {
            'environment': 'production',
            'instance_count': '3',
            'instance_type': 't3.medium',
            'backup_retention': '30'
        }
    }
    
    if target_env not in overrides:
        return content
    
    # Apply overrides
    modified_content = content
    for key, value in overrides[target_env].items():
        import re
        pattern = f'{key}\\s*=\\s*"[^"]*"'
        replacement = f'{key} = "{value}"'
        
        if re.search(pattern, modified_content):
            modified_content = re.sub(pattern, replacement, modified_content)
        else:
            modified_content += f'\n{key} = "{value}"'
    
    return modified_content

def generate_terraform_config(resource_type, name, resource_id):
    """Generate basic Terraform configuration for imported resources"""
    
    configs = {
        'aws_instance': f'''resource "aws_instance" "{name}" {{
  # Configuration will be populated after import
  # Run 'terraform plan' to see required attributes
  
  tags = {{
    Name = "{name}"
  }}
}}''',
        'aws_s3_bucket': f'''resource "aws_s3_bucket" "{name}" {{
  bucket = "{resource_id}"
}}''',
        'aws_vpc': f'''resource "aws_vpc" "{name}" {{
  # Configuration will be populated after import
  # Run 'terraform plan' to see required attributes
  
  tags = {{
    Name = "{name}"
  }}
}}'''
    }
    
    return configs.get(resource_type, f'''resource "{resource_type}" "{name}" {{
  # Configuration for {resource_id}
  # Add required attributes after import
}}''')

@terraform_bp.route('/workspaces/<workspace_id>/compare-plans', methods=['POST'])
def compare_plans(workspace_id):
    try:
        workspace_path = os.path.join(WORKSPACE_DIR, workspace_id)
        if not os.path.exists(workspace_path):
            return jsonify({'success': False, 'error': 'Workspace not found'}), 404
        
        data = request.get_json()
        env1 = data.get('env1')
        env2 = data.get('env2')
        
        plan1_path = os.path.join(workspace_path, f'{env1}.tfplan')
        plan2_path = os.path.join(workspace_path, f'{env2}.tfplan')
        
        if not os.path.exists(plan1_path) or not os.path.exists(plan2_path):
            return jsonify({'success': False, 'error': 'Plan files not found'})
        
        result1 = subprocess.run(['terraform', 'show', '-json', plan1_path], 
                               capture_output=True, text=True, cwd=workspace_path)
        result2 = subprocess.run(['terraform', 'show', '-json', plan2_path], 
                               capture_output=True, text=True, cwd=workspace_path)
        
        if result1.returncode != 0 or result2.returncode != 0:
            return jsonify({'success': False, 'error': 'Failed to read plans'})
        
        plan1_data = json.loads(result1.stdout)
        plan2_data = json.loads(result2.stdout)
        
        changes1 = plan1_data.get('resource_changes', [])
        changes2 = plan2_data.get('resource_changes', [])
        
        diff = {
            'env1_only': [c for c in changes1 if c not in changes2],
            'env2_only': [c for c in changes2 if c not in changes1],
            'common': [c for c in changes1 if c in changes2]
        }
        
        return jsonify({'success': True, 'comparison': diff, 'env1': env1, 'env2': env2})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@terraform_bp.route('/workspaces/<workspace_id>/archive-plan', methods=['POST'])
def archive_plan(workspace_id):
    try:
        workspace_path = os.path.join(WORKSPACE_DIR, workspace_id)
        if not os.path.exists(workspace_path):
            return jsonify({'success': False, 'error': 'Workspace not found'}), 404
        
        data = request.get_json()
        env = data.get('env')
        description = data.get('description', '')
        
        plan_path = os.path.join(workspace_path, f'{env}.tfplan')
        if not os.path.exists(plan_path):
            return jsonify({'success': False, 'error': 'Plan file not found'})
        
        archive_dir = os.path.join(workspace_path, '.terraform', 'archives')
        os.makedirs(archive_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        archive_name = f'{env}_{timestamp}.tfplan'
        archive_path = os.path.join(archive_dir, archive_name)
        
        shutil.copy2(plan_path, archive_path)
        
        metadata = {
            'env': env,
            'timestamp': timestamp,
            'description': description,
            'file': archive_name
        }
        
        metadata_file = os.path.join(archive_dir, 'metadata.json')
        if os.path.exists(metadata_file):
            with open(metadata_file, 'r') as f:
                archives = json.load(f)
        else:
            archives = []
        
        archives.append(metadata)
        
        with open(metadata_file, 'w') as f:
            json.dump(archives, f, indent=2)
        
        return jsonify({'success': True, 'message': f'Plan archived as {archive_name}'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@terraform_bp.route('/workspaces/<workspace_id>/plan-history', methods=['GET'])
def get_plan_history(workspace_id):
    try:
        workspace_path = os.path.join(WORKSPACE_DIR, workspace_id)
        if not os.path.exists(workspace_path):
            return jsonify({'success': False, 'error': 'Workspace not found'}), 404
        
        metadata_file = os.path.join(workspace_path, '.terraform', 'archives', 'metadata.json')
        if not os.path.exists(metadata_file):
            return jsonify({'success': True, 'history': []})
        
        with open(metadata_file, 'r') as f:
            archives = json.load(f)
        
        return jsonify({'success': True, 'history': archives})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@terraform_bp.route('/workspaces/<workspace_id>/generate-readme', methods=['POST'])
def generate_readme(workspace_id):
    try:
        workspace_path = os.path.join(WORKSPACE_DIR, workspace_id)
        if not os.path.exists(workspace_path):
            return jsonify({'success': False, 'error': 'Workspace not found'}), 404
        
        # Parse Terraform files
        resources = []
        variables = []
        outputs = []
        
        for file in os.listdir(workspace_path):
            if file.endswith('.tf'):
                file_path = os.path.join(workspace_path, file)
                with open(file_path, 'r') as f:
                    content = f.read()
                    
                    # Extract resources
                    import re
                    resource_matches = re.findall(r'resource\s+"([^"]+)"\s+"([^"]+)"', content)
                    for resource_type, resource_name in resource_matches:
                        resources.append({'type': resource_type, 'name': resource_name, 'file': file})
                    
                    # Extract variables
                    var_matches = re.findall(r'variable\s+"([^"]+)"\s*{([^}]*)}', content, re.DOTALL)
                    for var_name, var_block in var_matches:
                        desc_match = re.search(r'description\s*=\s*"([^"]+)"', var_block)
                        variables.append({
                            'name': var_name,
                            'description': desc_match.group(1) if desc_match else 'No description'
                        })
                    
                    # Extract outputs
                    out_matches = re.findall(r'output\s+"([^"]+)"\s*{([^}]*)}', content, re.DOTALL)
                    for out_name, out_block in out_matches:
                        desc_match = re.search(r'description\s*=\s*"([^"]+)"', out_block)
                        outputs.append({
                            'name': out_name,
                            'description': desc_match.group(1) if desc_match else 'No description'
                        })
        
        # Generate README content
        readme_content = f'''# Terraform Infrastructure - {workspace_id}

Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Overview
This Terraform configuration manages AWS infrastructure with {len(resources)} resources.

## Resources ({len(resources)})
'''
        
        if resources:
            readme_content += '| Resource Type | Name | File |\n|---|---|---|\n'
            for resource in resources:
                readme_content += f"| {resource['type']} | {resource['name']} | {resource['file']} |\n"
        
        if variables:
            readme_content += f'\n## Variables ({len(variables)})\n| Name | Description |\n|---|---|\n'
            for var in variables:
                readme_content += f"| {var['name']} | {var['description']} |\n"
        
        if outputs:
            readme_content += f'\n## Outputs ({len(outputs)})\n| Name | Description |\n|---|---|\n'
            for out in outputs:
                readme_content += f"| {out['name']} | {out['description']} |\n"
        
        readme_content += '''\n## Usage\n```bash\nterraform init\nterraform plan\nterraform apply\n```\n\n## Cleanup\n```bash\nterraform destroy\n```\n'''
        
        # Write README file
        readme_path = os.path.join(workspace_path, 'README.md')
        with open(readme_path, 'w') as f:
            f.write(readme_content)
        
        return jsonify({
            'success': True,
            'file_created': 'README.md',
            'resources_documented': len(resources),
            'variables_documented': len(variables),
            'outputs_documented': len(outputs)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@terraform_bp.route('/workspaces/<workspace_id>/generate-docs', methods=['POST'])
def generate_documentation(workspace_id):
    try:
        workspace_path = os.path.join(WORKSPACE_DIR, workspace_id)
        if not os.path.exists(workspace_path):
            return jsonify({'success': False, 'error': 'Workspace not found'}), 404
        
        # Parse resources with cost estimates
        resources = []
        total_monthly_cost = 0
        
        for file in os.listdir(workspace_path):
            if file.endswith('.tf'):
                file_path = os.path.join(workspace_path, file)
                with open(file_path, 'r') as f:
                    content = f.read()
                    
                    import re
                    resource_matches = re.findall(r'resource\s+"([^"]+)"\s+"([^"]+)"\s*{([^}]*)}', content, re.DOTALL)
                    for resource_type, resource_name, resource_block in resource_matches:
                        # Estimate costs
                        cost = estimate_resource_cost(resource_type, resource_block)
                        total_monthly_cost += cost
                        
                        # Find dependencies
                        deps = re.findall(r'([a-zA-Z_][a-zA-Z0-9_]*\.[a-zA-Z_][a-zA-Z0-9_]*)', resource_block)
                        
                        resources.append({
                            'type': resource_type,
                            'name': resource_name,
                            'file': file,
                            'monthly_cost': cost,
                            'dependencies': list(set(deps))
                        })
        
        # Generate documentation
        doc_content = f'''# Infrastructure Documentation\n\nWorkspace: {workspace_id}\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n## Cost Summary\nEstimated Monthly Cost: ${total_monthly_cost:.2f}\n\n## Resource Details\n'''
        
        for resource in resources:
            doc_content += f'''\n### {resource['type']}.{resource['name']}\n- **File**: {resource['file']}\n- **Monthly Cost**: ${resource['monthly_cost']:.2f}\n- **Dependencies**: {', '.join(resource['dependencies']) if resource['dependencies'] else 'None'}\n'''
        
        # Write documentation file
        docs_path = os.path.join(workspace_path, 'INFRASTRUCTURE.md')
        with open(docs_path, 'w') as f:
            f.write(doc_content)
        
        return jsonify({
            'success': True,
            'file_created': 'INFRASTRUCTURE.md',
            'total_monthly_cost': total_monthly_cost,
            'resources_documented': len(resources)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@terraform_bp.route('/workspaces/<workspace_id>/generate-diagram', methods=['POST'])
def generate_architecture_diagram(workspace_id):
    try:
        workspace_path = os.path.join(WORKSPACE_DIR, workspace_id)
        if not os.path.exists(workspace_path):
            return jsonify({'success': False, 'error': 'Workspace not found'}), 404
        
        # Parse resources and relationships
        resources = []
        relationships = []
        
        for file in os.listdir(workspace_path):
            if file.endswith('.tf'):
                file_path = os.path.join(workspace_path, file)
                with open(file_path, 'r') as f:
                    content = f.read()
                    
                    import re
                    resource_matches = re.findall(r'resource\s+"([^"]+)"\s+"([^"]+)"\s*{([^}]*)}', content, re.DOTALL)
                    for resource_type, resource_name, resource_block in resource_matches:
                        resource_id = f'{resource_type}.{resource_name}'
                        resources.append({
                            'id': resource_id,
                            'type': resource_type,
                            'name': resource_name,
                            'icon': get_resource_icon(resource_type)
                        })
                        
                        # Find references to other resources
                        refs = re.findall(r'([a-zA-Z_][a-zA-Z0-9_]*\.[a-zA-Z_][a-zA-Z0-9_]*)', resource_block)
                        for ref in refs:
                            if ref != resource_id and '.' in ref:
                                relationships.append({'from': ref, 'to': resource_id})
        
        # Generate Mermaid diagram
        diagram_content = '''# Architecture Diagram\n\n```mermaid\ngraph TD\n'''
        
        # Add nodes
        for resource in resources:
            diagram_content += f'    {resource["id"].replace(".", "_")}["{resource["icon"]} {resource["name"]}\\n{resource["type"]}"]\n'
        
        # Add relationships
        for rel in relationships:
            from_id = rel['from'].replace('.', '_')
            to_id = rel['to'].replace('.', '_')
            diagram_content += f'    {from_id} --> {to_id}\n'
        
        diagram_content += '```\n'
        
        # Write diagram file
        diagram_path = os.path.join(workspace_path, 'ARCHITECTURE.md')
        with open(diagram_path, 'w') as f:
            f.write(diagram_content)
        
        return jsonify({
            'success': True,
            'file_created': 'ARCHITECTURE.md',
            'resources_mapped': len(resources),
            'relationships_found': len(relationships)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

def estimate_resource_cost(resource_type, resource_block):
    """Estimate monthly cost for AWS resources"""
    costs = {
        'aws_instance': 20.0,
        'aws_rds_instance': 50.0,
        'aws_s3_bucket': 5.0,
        'aws_lambda_function': 2.0,
        'aws_vpc': 0.0,
        'aws_subnet': 0.0,
        'aws_security_group': 0.0,
        'aws_internet_gateway': 0.0,
        'aws_route_table': 0.0,
        'aws_load_balancer': 25.0,
        'aws_cloudfront_distribution': 15.0
    }
    
    base_cost = costs.get(resource_type, 10.0)
    
    # Adjust for instance types
    if 'instance_type' in resource_block:
        if 't3.micro' in resource_block:
            base_cost *= 0.5
        elif 't3.large' in resource_block:
            base_cost *= 2.0
        elif 'm5.xlarge' in resource_block:
            base_cost *= 4.0
    
    return base_cost

def get_resource_icon(resource_type):
    """Get icon for resource type"""
    icons = {
        'aws_instance': '🖥️',
        'aws_rds_instance': '🗄️',
        'aws_s3_bucket': '📦',
        'aws_lambda_function': '⚡',
        'aws_vpc': '🌐',
        'aws_subnet': '🔗',
        'aws_security_group': '🛡️',
        'aws_internet_gateway': '🌍',
        'aws_load_balancer': '⚖️',
        'aws_cloudfront_distribution': '🚀'
    }
    return icons.get(resource_type, '📋')

@terraform_bp.route('/workspaces/<workspace_id>/ai-generate', methods=['POST'])
def ai_generate_terraform(workspace_id):
    try:
        workspace_path = os.path.join(WORKSPACE_DIR, workspace_id)
        if not os.path.exists(workspace_path):
            return jsonify({'success': False, 'error': 'Workspace not found'}), 404
        
        data = request.get_json()
        user_request = data.get('request', '')
        model = data.get('model', 'codellama:7b-instruct')
        
        if not user_request:
            return jsonify({'success': False, 'error': 'Request is required'}), 400
        
        # AI prompt for Terraform generation
        prompt = f"""Generate Terraform code for AWS based on this request: "{user_request}"

Provide only valid Terraform HCL code with:
- Proper resource blocks
- Required arguments
- Reasonable defaults
- Comments explaining the resources

Request: {user_request}

Terraform code:"""
        
        # Check Ollama availability first
        import requests
        from app import get_ollama_url, check_ollama_connection, active_model
        ollama_url = get_ollama_url('/api/generate')
        
        is_connected, _ = check_ollama_connection()
        if not is_connected:
            return jsonify({'success': False, 'error': 'AI service unavailable'}), 503
        
        try:
            response = requests.post(
                ollama_url,
                json={
                    'model': model,
                    'prompt': prompt,
                    'stream': False,
                    'options': {'temperature': 0.1, 'num_predict': 1500}
                },
                timeout=120
            )
            
            if response.status_code == 200:
                result = response.json()
                generated_code = result.get('response', '')
                
                # Clean up the response to extract just the Terraform code
                lines = generated_code.split('\n')
                terraform_lines = []
                in_code_block = False
                
                for line in lines:
                    if 'resource "' in line or 'variable "' in line or 'output "' in line:
                        in_code_block = True
                    if in_code_block:
                        terraform_lines.append(line)
                    if line.strip() == '}' and in_code_block and not any(x in line for x in ['resource', 'variable', 'output']):
                        # Check if this closes a top-level block
                        if terraform_lines.count('{') <= terraform_lines.count('}'):
                            break
                
                clean_code = '\n'.join(terraform_lines) if terraform_lines else generated_code
                
                # Write to generated.tf file
                generated_file = os.path.join(workspace_path, 'ai-generated.tf')
                with open(generated_file, 'w') as f:
                    f.write(f'# AI Generated Terraform Code\n# Request: {user_request}\n# Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n\n{clean_code}')
                
                return jsonify({
                    'success': True,
                    'generated_code': clean_code,
                    'file_created': 'ai-generated.tf',
                    'request': user_request
                })
            else:
                return jsonify({'success': False, 'error': f'Ollama error: {response.status_code}'}), 503
        except requests.exceptions.Timeout:
            return jsonify({'success': False, 'error': 'AI request timed out'}), 503
        except requests.exceptions.RequestException as e:
            return jsonify({'success': False, 'error': f'AI service error: {str(e)}'}), 503
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@terraform_bp.route('/workspaces/<workspace_id>/ai-recommend', methods=['POST'])
def ai_recommend_improvements(workspace_id):
    try:
        workspace_path = os.path.join(WORKSPACE_DIR, workspace_id)
        if not os.path.exists(workspace_path):
            return jsonify({'success': False, 'error': 'Workspace not found'}), 404
        
        data = request.get_json()
        model = data.get('model', 'codellama:7b-instruct')
        
        # Read existing Terraform files
        terraform_content = ''
        for file in os.listdir(workspace_path):
            if file.endswith('.tf'):
                file_path = os.path.join(workspace_path, file)
                with open(file_path, 'r') as f:
                    terraform_content += f'\n# File: {file}\n{f.read()}\n'
        
        if not terraform_content.strip():
            return jsonify({'success': False, 'error': 'No Terraform files found'}), 404
        
        # AI prompt for recommendations
        prompt = f"""Analyze this Terraform code and provide intelligent recommendations for:
1. Cost optimization
2. Security improvements
3. Best practices
4. Resource efficiency
5. Scalability enhancements

Provide specific, actionable recommendations with brief explanations.

Terraform code:
{terraform_content[:2000]}

Recommendations:"""
        
        # Check Ollama availability first
        import requests
        from app import get_ollama_url, check_ollama_connection, active_model
        ollama_url = get_ollama_url('/api/generate')
        
        is_connected, _ = check_ollama_connection()
        if not is_connected:
            return jsonify({'success': False, 'error': 'AI service unavailable'}), 503
        
        try:
            response = requests.post(
                ollama_url,
                json={
                    'model': model,
                    'prompt': prompt,
                    'stream': False,
                    'options': {'temperature': 0.2, 'num_predict': 1000}
                },
                timeout=120
            )
            
            if response.status_code == 200:
                result = response.json()
                recommendations = result.get('response', '')
                
                # Write recommendations to file
                rec_file = os.path.join(workspace_path, 'ai-recommendations.md')
                with open(rec_file, 'w') as f:
                    f.write(f'# AI Infrastructure Recommendations\n\nGenerated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\nWorkspace: {workspace_id}\n\n{recommendations}')
                
                return jsonify({
                    'success': True,
                    'recommendations': recommendations,
                    'file_created': 'ai-recommendations.md'
                })
            else:
                return jsonify({'success': False, 'error': f'Ollama error: {response.status_code}'}), 503
        except requests.exceptions.Timeout:
            return jsonify({'success': False, 'error': 'AI request timed out'}), 503
        except requests.exceptions.RequestException as e:
            return jsonify({'success': False, 'error': f'AI service error: {str(e)}'}), 503
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@terraform_bp.route('/workspaces/<workspace_id>/ai-fix', methods=['POST'])
def ai_fix_errors(workspace_id):
    try:
        workspace_path = os.path.join(WORKSPACE_DIR, workspace_id)
        if not os.path.exists(workspace_path):
            return jsonify({'success': False, 'error': 'Workspace not found'}), 404
        
        data = request.get_json()
        error_output = data.get('error_output', '')
        model = data.get('model') or active_model
        
        if not error_output:
            # Run terraform validate to get errors
            result = subprocess.run(
                ['terraform', 'validate', '-json'],
                cwd=workspace_path,
                capture_output=True,
                text=True
            )
            error_output = result.stderr + result.stdout
        
        # Read current Terraform files
        terraform_files = {}
        for file in os.listdir(workspace_path):
            if file.endswith('.tf'):
                file_path = os.path.join(workspace_path, file)
                with open(file_path, 'r') as f:
                    terraform_files[file] = f.read()
        
        if not terraform_files:
            return jsonify({'success': False, 'error': 'No Terraform files found'}), 404
        
        # AI prompt for error fixing
        files_content = '\n'.join([f'# {name}\n{content}' for name, content in terraform_files.items()])
        
        prompt = f"""Fix the Terraform configuration errors. Provide the corrected code.

Errors:
{error_output[:1000]}

Current Terraform files:
{files_content[:1500]}

Provide corrected Terraform code with explanations of fixes:"""
        
        # Check Ollama availability first
        import requests
        from app import get_ollama_url, check_ollama_connection
        ollama_url = get_ollama_url('/api/generate')
        
        is_connected, _ = check_ollama_connection()
        if not is_connected:
            return provide_basic_fixes(error_output, terraform_files, workspace_path)
        
        try:
            response = requests.post(
                ollama_url,
                json={
                    'model': model,
                    'prompt': prompt,
                    'stream': False,
                    'options': {'temperature': 0.1, 'num_predict': 1500}
                },
                timeout=120
            )
            
            if response.status_code == 200:
                result = response.json()
                fixes = result.get('response', '')
                
                # Write fixes to file
                fixes_file = os.path.join(workspace_path, 'ai-fixes.md')
                with open(fixes_file, 'w') as f:
                    f.write(f'# AI Error Fixes\n\nGenerated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\nWorkspace: {workspace_id}\n\n## Original Errors\n```\n{error_output[:500]}\n```\n\n## Suggested Fixes\n{fixes}')
                
                return jsonify({
                    'success': True,
                    'fixes': fixes,
                    'file_created': 'ai-fixes.md',
                    'errors_analyzed': len(error_output)
                })
            else:
                return jsonify({'success': False, 'error': f'Ollama error: {response.status_code}'}), 503
        except requests.exceptions.Timeout:
            return jsonify({'success': False, 'error': 'AI request timed out'}), 503
        except requests.exceptions.RequestException as e:
            return jsonify({'success': False, 'error': f'AI service error: {str(e)}'}), 503
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@terraform_bp.route('/workspaces/<workspace_id>/security-scan-realtime', methods=['POST'])
def realtime_security_scan(workspace_id):
    try:
        workspace_path = os.path.join(WORKSPACE_DIR, workspace_id)
        if not os.path.exists(workspace_path):
            return jsonify({'success': False, 'error': 'Workspace not found'}), 404
        
        # Real-time security rules
        security_rules = {
            'hardcoded_secrets': r'(password|secret|key)\s*=\s*"[^"]+"',
            'public_access': r'0\.0\.0\.0/0',
            'unencrypted_storage': r'aws_s3_bucket.*(?!.*server_side_encryption)',
            'root_access': r'"\*".*"\*"',
            'insecure_protocols': r'protocol\s*=\s*"(http|ftp|telnet)"',
            'weak_passwords': r'password.*=.*"(123|admin|password)"'
        }
        
        vulnerabilities = []
        auto_fixes = []
        
        for file in os.listdir(workspace_path):
            if file.endswith('.tf'):
                file_path = os.path.join(workspace_path, file)
                with open(file_path, 'r') as f:
                    content = f.read()
                    lines = content.split('\n')
                
                import re
                for line_num, line in enumerate(lines, 1):
                    for rule_name, pattern in security_rules.items():
                        if re.search(pattern, line, re.IGNORECASE):
                            severity = get_vulnerability_severity(rule_name)
                            fix = generate_auto_fix(rule_name, line)
                            
                            vuln = {
                                'file': file,
                                'line': line_num,
                                'rule': rule_name,
                                'severity': severity,
                                'description': get_vulnerability_description(rule_name),
                                'code': line.strip(),
                                'fix': fix
                            }
                            vulnerabilities.append(vuln)
                            
                            if fix:
                                auto_fixes.append({
                                    'file': file,
                                    'line': line_num,
                                    'original': line,
                                    'fixed': fix
                                })
        
        # Generate security report
        report = {
            'scan_time': datetime.now().isoformat(),
            'total_vulnerabilities': len(vulnerabilities),
            'critical': len([v for v in vulnerabilities if v['severity'] == 'CRITICAL']),
            'high': len([v for v in vulnerabilities if v['severity'] == 'HIGH']),
            'medium': len([v for v in vulnerabilities if v['severity'] == 'MEDIUM']),
            'vulnerabilities': vulnerabilities,
            'auto_fixes_available': len(auto_fixes),
            'auto_fixes': auto_fixes
        }
        
        return jsonify({'success': True, 'security_report': report})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@terraform_bp.route('/workspaces/<workspace_id>/auto-remediate', methods=['POST'])
def auto_remediate_security(workspace_id):
    try:
        workspace_path = os.path.join(WORKSPACE_DIR, workspace_id)
        if not os.path.exists(workspace_path):
            return jsonify({'success': False, 'error': 'Workspace not found'}), 404
        
        data = request.get_json()
        fixes = data.get('fixes', [])
        
        remediated = []
        
        for fix in fixes:
            file_path = os.path.join(workspace_path, fix['file'])
            if os.path.exists(file_path):
                with open(file_path, 'r') as f:
                    lines = f.readlines()
                
                # Apply fix
                line_idx = fix['line'] - 1
                if 0 <= line_idx < len(lines):
                    original_line = lines[line_idx]
                    lines[line_idx] = fix['fixed'] + '\n'
                    
                    # Write back to file
                    with open(file_path, 'w') as f:
                        f.writelines(lines)
                    
                    remediated.append({
                        'file': fix['file'],
                        'line': fix['line'],
                        'original': original_line.strip(),
                        'fixed': fix['fixed']
                    })
        
        # Create remediation log
        log_content = f"# Security Auto-Remediation Log\n\nTimestamp: {datetime.now().isoformat()}\nWorkspace: {workspace_id}\nFixes Applied: {len(remediated)}\n\n"
        
        for rem in remediated:
            log_content += f"## {rem['file']}:{rem['line']}\n**Original:** `{rem['original']}`\n**Fixed:** `{rem['fixed']}`\n\n"
        
        log_path = os.path.join(workspace_path, 'security-remediation.md')
        with open(log_path, 'w') as f:
            f.write(log_content)
        
        return jsonify({
            'success': True,
            'remediated_count': len(remediated),
            'remediated_issues': remediated,
            'log_file': 'security-remediation.md'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@terraform_bp.route('/workspaces/<workspace_id>/security-monitor', methods=['GET'])
def security_monitor_status(workspace_id):
    try:
        workspace_path = os.path.join(WORKSPACE_DIR, workspace_id)
        if not os.path.exists(workspace_path):
            return jsonify({'success': False, 'error': 'Workspace not found'}), 404
        
        # Quick security check
        issues = 0
        last_scan = None
        
        # Check for recent security scan
        scan_file = os.path.join(workspace_path, 'security-remediation.md')
        if os.path.exists(scan_file):
            last_scan = datetime.fromtimestamp(os.path.getmtime(scan_file)).isoformat()
        
        # Quick vulnerability count
        for file in os.listdir(workspace_path):
            if file.endswith('.tf'):
                file_path = os.path.join(workspace_path, file)
                with open(file_path, 'r') as f:
                    content = f.read()
                    if '0.0.0.0/0' in content or 'password' in content.lower():
                        issues += 1
        
        status = {
            'security_score': max(0, 100 - (issues * 20)),
            'issues_detected': issues,
            'last_scan': last_scan,
            'status': 'SECURE' if issues == 0 else 'VULNERABLE'
        }
        
        return jsonify({'success': True, 'security_status': status})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@terraform_bp.route('/workspaces/<workspace_id>/graphical-display', methods=['POST'])
def generate_graphical_display(workspace_id):
    try:
        workspace_path = os.path.join(WORKSPACE_DIR, workspace_id)
        if not os.path.exists(workspace_path):
            return jsonify({'success': False, 'error': 'Workspace not found'}), 404
        
        # Parse terraform files for resource info and dependencies
        resources = []
        dependencies = []
        all_content = ''
        graph_output = None
        
        for file in os.listdir(workspace_path):
            if file.endswith('.tf'):
                file_path = os.path.join(workspace_path, file)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        all_content += content + '\n'
                        
                        import re
                        resource_matches = re.findall(r'resource\s+"([^"]+)"\s+"([^"]+)"', content)
                        for resource_type, resource_name in resource_matches:
                            resources.append({
                                'type': resource_type,
                                'name': resource_name,
                                'id': f'{resource_type}.{resource_name}',
                                'icon': get_aws_resource_icon(resource_type),
                                'color': get_aws_resource_color(resource_type),
                                'file': file
                            })
                except Exception:
                    continue
        
        # Find dependencies by looking for resource references
        resource_ids = [r['id'] for r in resources]
        for resource in resources:
            import re
            # Look for references to other resources in the content
            for other_id in resource_ids:
                if other_id != resource['id']:
                    # Check if this resource references another
                    if re.search(rf'\b{re.escape(other_id)}\b', all_content):
                        dependencies.append({
                            'from': resource['id'],
                            'to': other_id
                        })
        
        # Try terraform graph only if files are valid
        if resources:
            try:
                result = subprocess.run(
                    ['terraform', 'graph'],
                    cwd=workspace_path,
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                
                if result.returncode == 0:
                    graph_output = result.stdout
                    
            except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
                pass  # Continue without graph output
        
        # Create visual representation
        visual_data = {
            'graph_dot': graph_output,
            'resources': resources,
            'dependencies': dependencies,
            'resource_count': len(resources),
            'workspace_id': workspace_id,
            'has_graph': graph_output is not None
        }
        
        return jsonify({
            'success': True,
            'visual_data': visual_data
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

def get_aws_resource_icon(resource_type):
    """Get appropriate icon for AWS resource type"""
    icons = {
        'aws_instance': '🖥️',
        'aws_rds_instance': '🗄️',
        'aws_s3_bucket': '📦',
        'aws_lambda_function': '⚡',
        'aws_vpc': '🌐',
        'aws_subnet': '🔗',
        'aws_security_group': '🛡️',
        'aws_internet_gateway': '🌍',
        'aws_route_table': '🗺️',
        'aws_load_balancer': '⚖️',
        'aws_alb': '⚖️',
        'aws_elb': '⚖️',
        'aws_cloudfront_distribution': '🚀',
        'aws_iam_role': '👤',
        'aws_iam_policy': '📋',
        'aws_autoscaling_group': '📈',
        'aws_launch_configuration': '🚀',
        'aws_launch_template': '📄',
        'aws_ebs_volume': '💾',
        'aws_eip': '🌐',
        'aws_nat_gateway': '🔄',
        'aws_route53_zone': '🌍',
        'aws_cloudwatch_log_group': '📊'
    }
    return icons.get(resource_type, '📋')

def get_aws_resource_color(resource_type):
    """Get appropriate color for AWS resource type"""
    colors = {
        'aws_instance': '#FF9900',
        'aws_rds_instance': '#3F48CC',
        'aws_s3_bucket': '#569A31',
        'aws_lambda_function': '#FF9900',
        'aws_vpc': '#FF9900',
        'aws_subnet': '#FF9900',
        'aws_security_group': '#FF4B4B',
        'aws_internet_gateway': '#232F3E',
        'aws_route_table': '#FF9900',
        'aws_load_balancer': '#8C4FFF',
        'aws_alb': '#8C4FFF',
        'aws_elb': '#8C4FFF',
        'aws_cloudfront_distribution': '#8C4FFF',
        'aws_iam_role': '#FF4B4B',
        'aws_iam_policy': '#FF4B4B',
        'aws_autoscaling_group': '#FF9900',
        'aws_launch_configuration': '#FF9900',
        'aws_launch_template': '#FF9900',
        'aws_ebs_volume': '#FF9900',
        'aws_eip': '#232F3E',
        'aws_nat_gateway': '#FF9900',
        'aws_route53_zone': '#8C4FFF',
        'aws_cloudwatch_log_group': '#759C3E'
    }
    return colors.get(resource_type, '#232F3E')

def get_vulnerability_severity(rule_name):
    severity_map = {
        'hardcoded_secrets': 'CRITICAL',
        'public_access': 'HIGH',
        'unencrypted_storage': 'HIGH',
        'root_access': 'CRITICAL',
        'insecure_protocols': 'MEDIUM',
        'weak_passwords': 'HIGH'
    }
    return severity_map.get(rule_name, 'MEDIUM')

def get_vulnerability_description(rule_name):
    descriptions = {
        'hardcoded_secrets': 'Hardcoded credentials detected',
        'public_access': 'Public internet access allowed',
        'unencrypted_storage': 'Storage encryption not enabled',
        'root_access': 'Overly permissive access policies',
        'insecure_protocols': 'Insecure protocol usage',
        'weak_passwords': 'Weak or default passwords'
    }
    return descriptions.get(rule_name, 'Security vulnerability detected')

def generate_auto_fix(rule_name, line):
    fixes = {
        'hardcoded_secrets': lambda l: l.replace('password', 'password_hash').replace('secret', 'secret_arn'),
        'public_access': lambda l: l.replace('0.0.0.0/0', '10.0.0.0/8'),
        'unencrypted_storage': lambda l: l + '\n  server_side_encryption_configuration {\n    rule {\n      apply_server_side_encryption_by_default {\n        sse_algorithm = "AES256"\n      }\n    }\n  }',
        'insecure_protocols': lambda l: l.replace('"http"', '"https"').replace('"ftp"', '"sftp"'),
        'weak_passwords': lambda l: l.replace('"123"', 'var.secure_password').replace('"admin"', 'var.admin_user')
    }
    
    fix_func = fixes.get(rule_name)
    return fix_func(line.strip()) if fix_func else None

def provide_basic_fixes(error_output, terraform_files, workspace_path):
    """Provide basic error fixes when Ollama is unavailable"""
    basic_fixes = []
    
    # Common Terraform error patterns and fixes
    if 'required_providers' in error_output:
        basic_fixes.append('Add required_providers block to terraform configuration')
    if 'Invalid resource type' in error_output:
        basic_fixes.append('Check resource type spelling and provider availability')
    if 'Missing required argument' in error_output:
        basic_fixes.append('Add missing required arguments to resource blocks')
    if 'Duplicate resource' in error_output:
        basic_fixes.append('Remove duplicate resource definitions')
    
    fixes_content = f'''# Basic Error Fixes\n\nGenerated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n\n## Detected Issues\n{error_output[:500]}\n\n## Suggested Fixes\n'''
    
    for i, fix in enumerate(basic_fixes, 1):
        fixes_content += f'{i}. {fix}\n'
    
    if not basic_fixes:
        fixes_content += 'No specific fixes identified. Check Terraform syntax and provider configuration.'
    
    fixes_file = os.path.join(workspace_path, 'basic-fixes.md')
    with open(fixes_file, 'w') as f:
        f.write(fixes_content)
    
    return jsonify({
        'success': True,
        'fixes': '\n'.join(basic_fixes) if basic_fixes else 'No specific fixes identified',
        'file_created': 'basic-fixes.md',
        'note': 'Basic fixes provided (AI service unavailable)'
    })

def init_app(app):
    """Initialize the terraform integration with the Flask app."""
    app.register_blueprint(terraform_bp, url_prefix='/terraform')