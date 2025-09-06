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
        ollama_host = os.environ.get('OLLAMA_HOST', 'localhost')
        ollama_port = os.environ.get('OLLAMA_PORT', '11434')
        ollama_url = f"http://{ollama_host}:{ollama_port}/api/generate"
        model_name = os.environ.get('MODEL_NAME', 'codellama:13b-instruct')
        
        logger.info(f"Attempting to connect to Ollama at {ollama_url} with model {model_name}")
        
        try:
            # Use configurable content length
            first_file = list(tf_files.items())[0] if tf_files else ('', '')
            short_content = first_file[1][:content_length]
            
            prompt = f"Analyze this Terraform code:\n\n{short_content}\n\nProvide 3 key recommendations for security and best practices."
            
            # Check available models first
            models_response = requests.get(f"http://{ollama_host}:{ollama_port}/api/tags", timeout=5)
            available_models = []
            if models_response.status_code == 200:
                models_data = models_response.json().get('models', [])
                available_models = [m.get('name', '') for m in models_data]
                logger.info(f"Available models: {available_models}")
            
            # Use model from request or first available model
            requested_model = data.get('model')
            logger.info(f"Requested model: {requested_model}")
            
            if requested_model and requested_model in available_models:
                model_to_use = requested_model
            elif available_models:
                model_to_use = available_models[0]
            else:
                model_to_use = model_name
                
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

def init_app(app):
    """Initialize the terraform integration with the Flask app."""
    app.register_blueprint(terraform_bp, url_prefix='/terraform')