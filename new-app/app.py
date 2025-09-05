import os
import logging
import time
import subprocess
import json
import threading
import platform
import requests
import psutil
import re
import zipfile
import tempfile
import shutil
import hashlib
from datetime import datetime
from pathlib import Path
from werkzeug.utils import secure_filename
from flask import Flask, render_template, request, jsonify, send_from_directory
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Ensure logs directory exists
os.makedirs(os.path.expanduser(os.environ.get('LOGS_DIR', '~/terraform-llm-assistant/logs')), exist_ok=True)

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)
logger.info("Starting LLM Assistant application")

# Configuration
UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', 'uploads')
MAX_CONTENT_LENGTH = int(os.environ.get('MAX_UPLOAD_SIZE', str(50 * 1024 * 1024)))  # 50MB default
ALLOWED_EXTENSIONS = {
    'zip', 'tar', 'gz', 'tgz',  # Archives
    'tf', 'hcl', 'tfvars',      # Terraform
    'yml', 'yaml',              # YAML configs
    'py', 'sh', 'ps1',          # Scripts
    'json', 'toml', 'ini',      # Config files
    'md', 'txt', 'rst',         # Documentation
    'dockerfile', 'env'         # Docker/env files
}

# Project structure patterns for VS Code and IntelliJ
PROJECT_INDICATORS = {
    'vscode': ['.vscode/', '.vscode/settings.json', '.vscode/launch.json'],
    'intellij': ['.idea/', '.idea/modules.xml', '.idea/workspace.xml', '*.iml'],
    'terraform': ['main.tf', 'variables.tf', 'outputs.tf', 'terraform.tfvars'],
    'ansible': ['playbook.yml', 'inventory/', 'roles/', 'ansible.cfg'],
    'python': ['requirements.txt', 'setup.py', 'pyproject.toml', '__pycache__/'],
    'docker': ['Dockerfile', 'docker-compose.yml', '.dockerignore'],
    'kubernetes': ['*.yaml', '*.yml', 'kustomization.yaml', 'helm/']
}

# File Change Tracker Class
class FileChangeTracker:
    def __init__(self):
        self.project_changes = {}  # session_id -> changes list
        self.file_hashes = {}      # session_id -> {file_path: hash}

    def initialize_project(self, session_id, project_dir):
        """Initialize tracking for a new project session"""
        self.project_changes[session_id] = []
        self.file_hashes[session_id] = {}

        # Calculate initial hashes for all files
        for root, dirs, files in os.walk(project_dir):
            for file in files:
                file_path = os.path.join(root, file)
                relative_path = os.path.relpath(file_path, project_dir)

                try:
                    content = read_file_content(file_path)
                    if content and not content.startswith('['):  # Skip binary/error files
                        file_hash = hashlib.md5(content.encode('utf-8')).hexdigest()
                        self.file_hashes[session_id][relative_path] = file_hash
                except Exception as e:
                    logger.warning(f"Could not hash file {relative_path}: {e}")

    def track_file_change(self, session_id, file_path, old_content, new_content, change_type='modified'):
        """Track a file change"""
        if session_id not in self.project_changes:
            self.project_changes[session_id] = []

        # Calculate content difference
        diff_summary = self._generate_diff_summary(old_content, new_content)

        change_record = {
            'timestamp': datetime.now().isoformat(),
            'file_path': file_path,
            'change_type': change_type,  # 'modified', 'created', 'deleted'
            'diff_summary': diff_summary,
            'old_hash': hashlib.md5(old_content.encode('utf-8')).hexdigest() if old_content else None,
            'new_hash': hashlib.md5(new_content.encode('utf-8')).hexdigest() if new_content else None,
            'lines_added': len([l for l in new_content.split('\n') if l.strip()]) if new_content else 0,
            'lines_removed': len([l for l in old_content.split('\n') if l.strip()]) if old_content else 0
        }

        self.project_changes[session_id].append(change_record)

        # Update file hash
        if session_id not in self.file_hashes:
            self.file_hashes[session_id] = {}

        if new_content:
            self.file_hashes[session_id][file_path] = change_record['new_hash']
        elif file_path in self.file_hashes[session_id]:
            del self.file_hashes[session_id][file_path]

        # Keep only last 50 changes to avoid memory bloat
        if len(self.project_changes[session_id]) > 50:
            self.project_changes[session_id] = self.project_changes[session_id][-50:]

        logger.info(f"Tracked {change_type} change to {file_path} in session {session_id}")

    def _generate_diff_summary(self, old_content, new_content):
        """Generate a human-readable summary of changes"""
        if not old_content:
            newline_count = len(new_content.split('\n'))
            return f"New file created with {newline_count} lines"

        if not new_content:
            return "File deleted"

        old_lines = old_content.split('\n')
        new_lines = new_content.split('\n')

        added_lines = len(new_lines) - len(old_lines)

        # Simple change detection
        if added_lines > 0:
            return f"Added {added_lines} lines of code"
        elif added_lines < 0:
            return f"Removed {abs(added_lines)} lines of code"
        else:
            # Same number of lines, check for modifications
            changes = sum(1 for old, new in zip(old_lines, new_lines) if old != new)
            if changes > 0:
                return f"Modified {changes} lines"
            else:
                return "File unchanged"

    def get_recent_changes(self, session_id, limit=10):
        """Get recent changes for a session"""
        if session_id not in self.project_changes:
            return []

        return self.project_changes[session_id][-limit:]

    def get_project_change_summary(self, session_id):
        """Get a summary of all changes in the project"""
        if session_id not in self.project_changes:
            return "No changes tracked"

        changes = self.project_changes[session_id]
        if not changes:
            return "No changes made to project files"

        # Group by file
        file_changes = {}
        for change in changes:
            file_path = change['file_path']
            if file_path not in file_changes:
                file_changes[file_path] = []
            file_changes[file_path].append(change)

        summary_parts = []
        summary_parts.append(f"Recent changes ({len(changes)} total):")

        for file_path, file_change_list in file_changes.items():
            latest_change = file_change_list[-1]
            change_count = len(file_change_list)

            summary_parts.append(f"- {file_path}: {latest_change['diff_summary']}")
            if change_count > 1:
                summary_parts.append(f"  ({change_count} changes total)")

        return '\n'.join(summary_parts)

# Create Flask app
app = Flask(__name__, static_folder='static', template_folder='templates')
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH

# Ensure upload directory exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Security: Validate secret key
secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key')
if secret_key == 'dev-secret-key' and os.environ.get('FLASK_ENV') == 'production':
    raise ValueError("Must set SECRET_KEY environment variable in production")
app.config['SECRET_KEY'] = secret_key
app.config['APP_TITLE'] = 'Terraform LLM Assistant'

# Get model configuration
active_model = os.environ.get('MODEL_NAME', 'codellama:13b-instruct')
ollama_host = os.environ.get('OLLAMA_HOST', 'localhost')
ollama_port = os.environ.get('OLLAMA_PORT', '11434')

# Check if auto-download is disabled
AUTO_DOWNLOAD_DISABLED = os.environ.get('DISABLE_AUTO_MODEL_DOWNLOAD', 'false').lower() in ('true', '1', 't')
if AUTO_DOWNLOAD_DISABLED:
    logger.info("Automatic model download is disabled by environment variable")

# Global instances
file_tracker = FileChangeTracker()

# Global variable to track download progress
download_progress = {
    'downloading': False,
    'model': None,
    'progress': 0,
    'status': 'idle',
    'total': 0,
    'completed': 0,
    'speed': '',
    'eta': '',
    'completion_time': 0,
    'file_name': None,
    'completed_layers': [],
    'layer_progress': {},
    'current_layer': None,
    'download_attempt': 0,
    'last_download_attempt_time': 0,
    'api_call_count': 0
}

# Cache for model status to reduce redundant checks
model_status_cache = {
    'timestamp': 0,
    'response': None,
    'cache_ttl': 3  # Cache time-to-live in seconds
}

def get_ollama_url(endpoint=''):
    """Helper function to construct Ollama URLs"""
    return f"http://{ollama_host}:{ollama_port}{endpoint}"

def check_ollama_connection(timeout=2):
    """Check if Ollama service is running and return connection status"""
    try:
        response = requests.get(get_ollama_url('/api/tags'), timeout=timeout)
        return response.status_code == 200, response
    except Exception as e:
        logger.warning(f"Ollama connection error: {e}")
        return False, None

def get_available_models():
    """Get list of available models from Ollama"""
    try:
        is_connected, response = check_ollama_connection()
        if is_connected:
            models_data = response.json().get('models', [])
            return [model.get('name') for model in models_data]
    except Exception as e:
        logger.warning(f"Error getting available models: {e}")
    return []

def is_model_available(model_id):
    """Check if a specific model is available"""
    available_models = get_available_models()
    model_base = model_id.split(':')[0] if ':' in model_id else model_id

    # Check for exact match first
    if model_id in available_models:
        return True

    # Check for base model match (e.g., 'codellama' matches 'codellama:13b-instruct')
    return any(m.startswith(model_base + ':') for m in available_models)

def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def extract_archive(archive_path, extract_to):
    """Extract archive files (zip, tar, etc.)"""
    try:
        if archive_path.endswith('.zip'):
            with zipfile.ZipFile(archive_path, 'r') as zip_ref:
                zip_ref.extractall(extract_to)
        elif archive_path.endswith(('.tar', '.tar.gz', '.tgz')):
            import tarfile
            with tarfile.open(archive_path, 'r:*') as tar_ref:
                tar_ref.extractall(extract_to)
        return True
    except Exception as e:
        logger.error(f"Error extracting archive {archive_path}: {e}")
        return False

def analyze_project_structure(project_path):
    """Analyze project structure and detect technologies"""
    project_path = Path(project_path)
    analysis = {
        'project_type': [],
        'technologies': [],
        'structure': {},
        'files': [],
        'ide_config': {},
        'recommendations': []
    }

    # Collect all files
    all_files = []
    for root, dirs, files in os.walk(project_path):
        # Skip hidden directories and common ignore patterns
        dirs[:] = [d for d in dirs if not d.startswith('.') or d in ['.vscode', '.idea']]

        for file in files:
            file_path = Path(root) / file
            relative_path = file_path.relative_to(project_path)
            all_files.append(str(relative_path))

    analysis['files'] = all_files

    # Detect project types and technologies
    for project_type, indicators in PROJECT_INDICATORS.items():
        for indicator in indicators:
            if any(str(f).endswith(indicator.replace('*', '')) or
                   str(f).startswith(indicator.replace('/', '')) for f in all_files):
                if project_type not in analysis['project_type']:
                    analysis['project_type'].append(project_type)

    # Analyze IDE configurations
    vscode_files = [f for f in all_files if f.startswith('.vscode/')]
    if vscode_files:
        analysis['ide_config']['vscode'] = vscode_files

    intellij_files = [f for f in all_files if f.startswith('.idea/') or f.endswith('.iml')]
    if intellij_files:
        analysis['ide_config']['intellij'] = intellij_files

    # Create structure tree
    analysis['structure'] = create_file_tree(all_files)

    # Generate recommendations
    analysis['recommendations'] = generate_recommendations(analysis)

    return analysis

def create_file_tree(files):
    """Create a nested tree structure from file list"""
    tree = {}
    for file_path in files:
        parts = Path(file_path).parts
        current = tree
        for part in parts[:-1]:
            if part not in current:
                current[part] = {}
            current = current[part]
        # Add file
        current[parts[-1]] = None
    return tree

def generate_recommendations(analysis):
    """Generate recommendations based on project analysis"""
    recommendations = []

    if 'terraform' in analysis['project_type']:
        recommendations.append("Consider adding terraform.tfvars.example for variable documentation")
        recommendations.append("Add .terraform/ to .gitignore if not already present")
        if 'main.tf' in str(analysis['files']) and 'modules/' not in str(analysis['files']):
            recommendations.append("Consider modularizing your Terraform code for reusability")

    if 'ansible' in analysis['project_type']:
        recommendations.append("Use ansible-vault for sensitive variables")
        recommendations.append("Consider using requirements.yml for role dependencies")

    if 'docker' in analysis['project_type']:
        recommendations.append("Add .dockerignore to optimize build context")
        recommendations.append("Consider multi-stage builds for production images")

    if 'python' in analysis['project_type']:
        if 'requirements.txt' not in str(analysis['files']):
            recommendations.append("Add requirements.txt for Python dependencies")

    # IDE-specific recommendations
    if 'vscode' in analysis['ide_config']:
        recommendations.append("VS Code configuration detected - consider sharing workspace settings")

    if 'intellij' in analysis['ide_config']:
        recommendations.append("IntelliJ configuration detected - add *.iml to .gitignore")

    return recommendations

def read_file_content(file_path, max_size=1024*1024):  # 1MB limit
    """Safely read file content with size limit"""
    try:
        file_path = Path(file_path)
        if file_path.stat().st_size > max_size:
            return f"[File too large: {file_path.stat().st_size} bytes]"

        # Try to read as text
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except UnicodeDecodeError:
            # Try with different encoding
            try:
                with open(file_path, 'r', encoding='latin-1') as f:
                    return f.read()
            except:
                return "[Binary file or encoding error]"
    except Exception as e:
        return f"[Error reading file: {e}]"

def initialize_project_tracking(session_id, project_dir):
    """Initialize file tracking for uploaded project"""
    try:
        file_tracker.initialize_project(session_id, project_dir)
        logger.info(f"Initialized file tracking for session {session_id}")
    except Exception as e:
        logger.error(f"Error initializing file tracking: {e}")

def track_and_update_file(session_id, file_path, new_content, project_dir):
    """Helper function to track changes and update files"""
    full_file_path = os.path.join(project_dir, file_path)

    # Get old content if file exists
    old_content = ""
    change_type = "created"

    if os.path.exists(full_file_path):
        old_content = read_file_content(full_file_path)
        change_type = "modified"

    # Track the change
    file_tracker.track_file_change(session_id, file_path, old_content, new_content, change_type)

    # Write the new content
    file_dir = os.path.dirname(full_file_path)
    if file_dir and not os.path.exists(file_dir):
        os.makedirs(file_dir, exist_ok=True)

    with open(full_file_path, 'w', encoding='utf-8') as f:
        f.write(new_content)

def get_enhanced_chat_context(session_id, message):
    """Get enhanced context including recent file changes"""
    context_parts = []

    # Add project session info
    if session_id:
        context_parts.append(f"[Project Session: {session_id}]")

        # Add recent changes summary
        changes_summary = file_tracker.get_project_change_summary(session_id)
        if changes_summary != "No changes tracked" and changes_summary != "No changes made to project files":
            context_parts.append(f"[Recent File Changes]\n{changes_summary}")

        # Add recent changes details for more context
        recent_changes = file_tracker.get_recent_changes(session_id, 5)
        if recent_changes:
            context_parts.append("[Recent File Modifications]")
            for change in recent_changes[-3:]:  # Last 3 changes
                timestamp = change['timestamp']
                file_path = change['file_path']
                diff_summary = change['diff_summary']
                context_parts.append(f"- {timestamp}: {file_path} - {diff_summary}")

    # Add the user message
    context_parts.append(f"User: {message}")

    return "\n\n".join(context_parts)

@app.route('/')
def index():
    """Serve the main application page"""
    return render_template('index.html',
                           active_model=active_model,
                           app_title=app.config['APP_TITLE'])

@app.route('/file-browser')
def file_browser():
    """Serve the file browser interface"""
    return render_template('file_browser.html',
                           active_model=active_model,
                           app_title=app.config['APP_TITLE'])

@app.route('/static/<path:path>')
def serve_static(path):
    """Serve static files"""
    return send_from_directory('static', path)

@app.route('/api/download-progress', methods=['GET'])
def get_download_progress():
    """Get current download progress"""
    return jsonify(download_progress)

@app.route('/api/upload-project', methods=['POST'])
def upload_project():
    """Upload and analyze a project archive, individual files, or folder structure with change tracking"""
    try:
        if 'files' not in request.files:
            return jsonify({'success': False, 'error': 'No files provided'}), 400

        files = request.files.getlist('files')
        if not files or all(f.filename == '' for f in files):
            return jsonify({'success': False, 'error': 'No files selected'}), 400

        upload_type = request.form.get('upload_type', 'files')

        # Create temporary directory for this upload session
        session_id = str(int(time.time()))
        upload_session_dir = os.path.join(UPLOAD_FOLDER, session_id)
        os.makedirs(upload_session_dir, exist_ok=True)

        uploaded_files = []
        project_dir = upload_session_dir

        # Handle folder uploads differently to preserve structure
        if upload_type == 'folder':
            project_dir = os.path.join(upload_session_dir, 'project')
            os.makedirs(project_dir, exist_ok=True)

            for file in files:
                if file.filename == '':
                    continue

                # For folder uploads, the filename should contain the path
                # Use the original filename which includes the relative path for folders
                original_filename = file.filename

                # Clean the path but preserve directory structure
                path_parts = []
                for part in original_filename.split('/'):
                    if part and part != '..':  # Security: prevent directory traversal
                        secured_part = secure_filename(part)
                        if secured_part:
                            path_parts.append(secured_part)

                if not path_parts:
                    continue

                # Create the full file path
                file_path = os.path.join(project_dir, *path_parts)

                # Create directories if they don't exist
                file_dir = os.path.dirname(file_path)
                if file_dir:
                    os.makedirs(file_dir, exist_ok=True)

                # Save the file
                file.save(file_path)
                uploaded_files.append('/'.join(path_parts))

                logger.info(f"Saved folder file: {original_filename} -> {file_path}")

        else:
            # Handle individual files or archives
            for file in files:
                if file.filename == '':
                    continue

                filename = secure_filename(file.filename)
                if not filename:
                    continue

                # Save file
                file_path = os.path.join(upload_session_dir, filename)
                file.save(file_path)
                uploaded_files.append(filename)

                # If it's an archive, extract it
                if filename.lower().endswith(('.zip', '.tar', '.tar.gz', '.tgz')):
                    extract_dir = os.path.join(upload_session_dir, 'extracted')
                    os.makedirs(extract_dir, exist_ok=True)

                    if extract_archive(file_path, extract_dir):
                        project_dir = extract_dir
                        logger.info(f"Extracted archive {filename} to {extract_dir}")

        # Initialize file change tracking for this project
        initialize_project_tracking(session_id, project_dir)

        # Analyze the project structure
        try:
            analysis = analyze_project_structure(project_dir)
        except Exception as e:
            logger.error(f"Error analyzing project structure: {e}")
            return jsonify({
                'success': False,
                'error': f'Error analyzing project: {str(e)}'
            }), 500

        # Add upload metadata to analysis
        analysis['upload_info'] = {
            'type': upload_type,
            'session_id': session_id,
            'uploaded_files': uploaded_files,
            'total_files': len(uploaded_files)
        }

        # Store analysis for later reference
        analysis_file = os.path.join(upload_session_dir, 'analysis.json')
        with open(analysis_file, 'w') as f:
            json.dump(analysis, f, indent=2)

        logger.info(f"Project upload completed - Type: {upload_type}, Files: {len(uploaded_files)}, Skipped: {len(skipped_files)}, Session: {session_id}")

        response_data = {
            'success': True,
            'session_id': session_id,
            'uploaded_files': uploaded_files,
            'skipped_files': skipped_files,
            'upload_type': upload_type,
            'analysis': analysis,
            'tracking_initialized': True,
            'total_size_mb': round(total_size_mb, 2)
        }

        return jsonify(response_data)

    except Exception as e:
        logger.error(f"Error in upload_project: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/project/<session_id>/files', methods=['GET'])
def get_project_files(session_id):
    """Get list of files in uploaded project"""
    try:
        session_dir = os.path.join(UPLOAD_FOLDER, session_id)
        if not os.path.exists(session_dir):
            return jsonify({'success': False, 'error': 'Session not found'}), 404

        # Check for extracted directory first
        project_dir = os.path.join(session_dir, 'extracted')
        if not os.path.exists(project_dir):
            project_dir = os.path.join(session_dir, 'project')
        if not os.path.exists(project_dir):
            project_dir = session_dir

        analysis = analyze_project_structure(project_dir)

        return jsonify({
            'success': True,
            'files': analysis['files'],
            'structure': analysis['structure'],
            'project_type': analysis['project_type'],
            'technologies': analysis['technologies']
        })

    except Exception as e:
        logger.error(f"Error getting project files: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/project/<session_id>/file/<path:file_path>', methods=['GET'])
def get_file_content(session_id, file_path):
    """Get content of a specific file"""
    try:
        session_dir = os.path.join(UPLOAD_FOLDER, session_id)
        if not os.path.exists(session_dir):
            return jsonify({'success': False, 'error': 'Session not found'}), 404

        # Check for extracted directory first
        project_dir = os.path.join(session_dir, 'extracted')
        if not os.path.exists(project_dir):
            project_dir = os.path.join(session_dir, 'project')
        if not os.path.exists(project_dir):
            project_dir = session_dir

        full_file_path = os.path.join(project_dir, file_path)

        # Security check - ensure file is within project directory
        if not os.path.commonpath([project_dir, full_file_path]) == project_dir:
            return jsonify({'success': False, 'error': 'Invalid file path'}), 400

        if not os.path.exists(full_file_path):
            return jsonify({'success': False, 'error': 'File not found'}), 404

        content = read_file_content(full_file_path)

        return jsonify({
            'success': True,
            'file_path': file_path,
            'content': content,
            'size': os.path.getsize(full_file_path)
        })

    except Exception as e:
        logger.error(f"Error getting file content: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/project/<session_id>/file/<path:file_path>', methods=['PUT'])
def update_file_content(session_id, file_path):
    """Update content of a specific file with change tracking"""
    try:
        session_dir = os.path.join(UPLOAD_FOLDER, session_id)
        if not os.path.exists(session_dir):
            return jsonify({'success': False, 'error': 'Session not found'}), 404

        data = request.get_json()
        new_content = data.get('content', '')

        # Determine project directory
        project_dir = os.path.join(session_dir, 'extracted')
        if not os.path.exists(project_dir):
            project_dir = os.path.join(session_dir, 'project')
        if not os.path.exists(project_dir):
            project_dir = session_dir

        full_file_path = os.path.join(project_dir, file_path)

        # Security check - ensure file is within project directory
        if not os.path.commonpath([project_dir, full_file_path]) == project_dir:
            return jsonify({'success': False, 'error': 'Invalid file path'}), 400

        # Use the tracking function
        track_and_update_file(session_id, file_path, new_content, project_dir)

        logger.info(f"Updated file: {file_path} in session {session_id}")

        return jsonify({
            'success': True,
            'message': f'File {file_path} updated successfully',
            'size': len(new_content.encode('utf-8'))
        })

    except Exception as e:
        logger.error(f"Error updating file content: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/project/<session_id>/file/<path:file_path>', methods=['DELETE'])
def delete_file(session_id, file_path):
    """Delete a specific file with change tracking"""
    try:
        session_dir = os.path.join(UPLOAD_FOLDER, session_id)
        if not os.path.exists(session_dir):
            return jsonify({'success': False, 'error': 'Session not found'}), 404

        # Determine project directory
        project_dir = os.path.join(session_dir, 'extracted')
        if not os.path.exists(project_dir):
            project_dir = os.path.join(session_dir, 'project')
        if not os.path.exists(project_dir):
            project_dir = session_dir

        full_file_path = os.path.join(project_dir, file_path)

        # Security check - ensure file is within project directory
        if not os.path.commonpath([project_dir, full_file_path]) == project_dir:
            return jsonify({'success': False, 'error': 'Invalid file path'}), 400

        if not os.path.exists(full_file_path):
            return jsonify({'success': False, 'error': 'File not found'}), 404

        # Get old content for tracking
        old_content = read_file_content(full_file_path)

        # Track the deletion
        file_tracker.track_file_change(session_id, file_path, old_content, "", "deleted")

        # Delete the file
        os.remove(full_file_path)
        logger.info(f"Deleted file: {file_path} from session {session_id}")

        return jsonify({
            'success': True,
            'message': f'File {file_path} deleted successfully'
        })

    except Exception as e:
        logger.error(f"Error deleting file: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/project/<session_id>/file', methods=['POST'])
def create_new_file(session_id):
    """Create a new file in the project with change tracking"""
    try:
        session_dir = os.path.join(UPLOAD_FOLDER, session_id)
        if not os.path.exists(session_dir):
            return jsonify({'success': False, 'error': 'Session not found'}), 404

        data = request.get_json()
        file_path = data.get('file_path', '').strip()
        content = data.get('content', '')

        if not file_path:
            return jsonify({'success': False, 'error': 'File path is required'}), 400

        # Validate file path
        if '..' in file_path or file_path.startswith('/'):
            return jsonify({'success': False, 'error': 'Invalid file path'}), 400

        # Determine project directory
        project_dir = os.path.join(session_dir, 'extracted')
        if not os.path.exists(project_dir):
            project_dir = os.path.join(session_dir, 'project')
        if not os.path.exists(project_dir):
            project_dir = session_dir

        full_file_path = os.path.join(project_dir, file_path)

        # Security check - ensure file is within project directory
        if not os.path.commonpath([project_dir, full_file_path]) == project_dir:
            return jsonify({'success': False, 'error': 'Invalid file path'}), 400

        # Check if file already exists
        if os.path.exists(full_file_path):
            return jsonify({'success': False, 'error': 'File already exists'}), 409

        # Use the tracking function
        track_and_update_file(session_id, file_path, content, project_dir)

        logger.info(f"Created new file: {file_path} in session {session_id}")

        return jsonify({
            'success': True,
            'message': f'File {file_path} created successfully',
            'file_path': file_path,
            'size': len(content.encode('utf-8'))
        })

    except Exception as e:
        logger.error(f"Error creating new file: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/project/<session_id>/changes', methods=['GET'])
def get_project_changes(session_id):
    """Get recent changes for a project"""
    try:
        limit = int(request.args.get('limit', 10))
        changes = file_tracker.get_recent_changes(session_id, limit)
        summary = file_tracker.get_project_change_summary(session_id)

        return jsonify({
            'success': True,
            'changes': changes,
            'summary': summary,
            'total_changes': len(file_tracker.project_changes.get(session_id, []))
        })
    except Exception as e:
        logger.error(f"Error getting project changes: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/project/<session_id>/changes/clear', methods=['POST'])
def clear_project_changes(session_id):
    """Clear change history for a project"""
    try:
        if session_id in file_tracker.project_changes:
            file_tracker.project_changes[session_id] = []

        return jsonify({
            'success': True,
            'message': 'Change history cleared'
        })
    except Exception as e:
        logger.error(f"Error clearing project changes: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/project/<session_id>/analyze', methods=['POST'])
def analyze_project_with_llm(session_id):
    """Analyze project using LLM with optional specific focus"""
    try:
        session_dir = os.path.join(UPLOAD_FOLDER, session_id)
        if not os.path.exists(session_dir):
            return jsonify({'success': False, 'error': 'Session not found'}), 404

        data = request.get_json() or {}
        focus = data.get('focus', 'general')  # general, security, optimization, etc.
        specific_files = data.get('files', [])  # specific files to analyze

        # Get project analysis
        project_dir = os.path.join(session_dir, 'extracted')
        if not os.path.exists(project_dir):
            project_dir = os.path.join(session_dir, 'project')
        if not os.path.exists(project_dir):
            project_dir = session_dir

        analysis = analyze_project_structure(project_dir)

        # Build context for LLM
        context = f"""Project Analysis Request:

Project Type: {', '.join(analysis['project_type'])}
Technologies: {', '.join(analysis['technologies'])}
Focus: {focus}

File Structure:
{json.dumps(analysis['structure'], indent=2)}

"""

        # Include recent changes if available
        changes_summary = file_tracker.get_project_change_summary(session_id)
        if changes_summary != "No changes tracked" and changes_summary != "No changes made to project files":
            context += f"\nRecent Changes:\n{changes_summary}\n"

        # Include specific file contents if requested
        if specific_files:
            context += "\nFile Contents:\n"
            for file_path in specific_files[:10]:  # Limit to 10 files
                full_path = os.path.join(project_dir, file_path)
                if os.path.exists(full_path):
                    content = read_file_content(full_path, max_size=50*1024)  # 50KB limit per file
                    context += f"\n--- {file_path} ---\n{content}\n"

        # Create analysis prompt based on focus
        if focus == 'security':
            prompt = f"""Analyze this project for security issues and recommendations:

{context}

Please provide:
1. Security vulnerabilities or concerns
2. Best practices that should be implemented
3. Specific recommendations for improvement
4. Infrastructure security considerations
"""
        elif focus == 'optimization':
            prompt = f"""Analyze this project for optimization opportunities:

{context}

Please provide:
1. Performance optimization suggestions
2. Resource usage improvements
3. Infrastructure cost optimizations
4. Code organization recommendations
"""
        else:
            prompt = f"""Analyze this infrastructure project:

{context}

Please provide:
1. Overview of the project structure and purpose
2. Infrastructure patterns and technologies used
3. Best practices and recommendations
4. Potential improvements or concerns
"""

        # Send to LLM if available
        is_connected, _ = check_ollama_connection()
        if is_connected:
            try:
                response = requests.post(
                    get_ollama_url('/api/generate'),
                    json={
                        'model': active_model,
                        'prompt': prompt,
                        'stream': False,
                        'options': {
                            'temperature': 0.1,
                            'top_p': 0.9,
                            'top_k': 40
                        }
                    },
                    timeout=120
                )

                if response.status_code == 200:
                    result = response.json()
                    llm_response = result.get('response', '')

                    return jsonify({
                        'success': True,
                        'analysis': llm_response,
                        'project_info': {
                            'type': analysis['project_type'],
                            'technologies': analysis['technologies'],
                            'file_count': len(analysis['files']),
                            'recommendations': analysis['recommendations']
                        }
                    })

            except Exception as e:
                logger.error(f"LLM analysis error: {e}")

        # Fallback response if LLM not available
        return jsonify({
            'success': True,
            'analysis': "LLM analysis not available. Here's the basic project analysis:",
            'project_info': {
                'type': analysis['project_type'],
                'technologies': analysis['technologies'],
                'file_count': len(analysis['files']),
                'recommendations': analysis['recommendations'],
                'structure': analysis['structure']
            }
        })

    except Exception as e:
        logger.error(f"Error in project analysis: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/project/<session_id>/cleanup', methods=['DELETE'])
def cleanup_project(session_id):
    """Clean up uploaded project files"""
    try:
        session_dir = os.path.join(UPLOAD_FOLDER, session_id)
        if os.path.exists(session_dir):
            shutil.rmtree(session_dir)
            return jsonify({'success': True, 'message': 'Project files cleaned up'})
        else:
            return jsonify({'success': False, 'error': 'Session not found'}), 404
    except Exception as e:
        logger.error(f"Error cleaning up project: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/projects', methods=['GET'])
def list_projects():
    """List all uploaded project sessions"""
    try:
        if not os.path.exists(UPLOAD_FOLDER):
            return jsonify({'success': True, 'projects': []})

        projects = []
        for session_id in os.listdir(UPLOAD_FOLDER):
            session_dir = os.path.join(UPLOAD_FOLDER, session_id)
            if os.path.isdir(session_dir):
                # Get session info
                analysis_file = os.path.join(session_dir, 'analysis.json')
                if os.path.exists(analysis_file):
                    try:
                        with open(analysis_file, 'r') as f:
                            analysis = json.load(f)

                        projects.append({
                            'session_id': session_id,
                            'created': os.path.getctime(session_dir),
                            'project_type': analysis.get('project_type', []),
                            'file_count': len(analysis.get('files', [])),
                            'technologies': analysis.get('technologies', [])
                        })
                    except:
                        # If analysis file is corrupted, still list the session
                        projects.append({
                            'session_id': session_id,
                            'created': os.path.getctime(session_dir),
                            'project_type': ['unknown'],
                            'file_count': 0,
                            'technologies': []
                        })

        # Sort by creation time (newest first)
        projects.sort(key=lambda x: x['created'], reverse=True)

        return jsonify({'success': True, 'projects': projects})

    except Exception as e:
        logger.error(f"Error listing projects: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# Cleanup old project files periodically (older than 24 hours)
def cleanup_old_projects():
    """Clean up project files older than 24 hours"""
    try:
        if not os.path.exists(UPLOAD_FOLDER):
            return

        cutoff_time = time.time() - (24 * 60 * 60)  # 24 hours ago

        for session_id in os.listdir(UPLOAD_FOLDER):
            session_dir = os.path.join(UPLOAD_FOLDER, session_id)
            if os.path.isdir(session_dir):
                if os.path.getctime(session_dir) < cutoff_time:
                    shutil.rmtree(session_dir)
                    logger.info(f"Cleaned up old project session: {session_id}")
    except Exception as e:
        logger.error(f"Error in cleanup: {e}")

# Schedule cleanup to run periodically
def schedule_cleanup():
    """Schedule periodic cleanup of old files"""
    cleanup_old_projects()
    # Schedule next cleanup in 1 hour
    threading.Timer(3600, schedule_cleanup).start()

# Start cleanup scheduler
schedule_cleanup()

def parse_download_line(line):
    """Parse Ollama download progress line"""
    global download_progress

    line = line.strip()
    logger.debug(f"Download output: {line}")

    # Track layer downloads and extract ID to avoid reset
    layer_id = None
    if 'pulling' in line and '...' in line:
        layer_match = re.search(r'pulling\s+([a-f0-9]+)\.\.\.', line)
        if layer_match:
            layer_id = layer_match.group(1)
            download_progress['file_name'] = layer_id

            # Ensure completed_layers is initialized as a set
            if 'completed_layers' not in download_progress:
                download_progress['completed_layers'] = set()
            elif isinstance(download_progress['completed_layers'], list):
                download_progress['completed_layers'] = set(download_progress['completed_layers'])

            # Check if this is a new layer
            if layer_id not in download_progress['completed_layers']:
                download_progress['current_layer'] = layer_id

    # Process special status messages
    status_messages = {
        'pulling manifest': ('Initializing download...', 2),
        'verifying sha256 digest': ('Verifying download...', 95),
        'writing manifest': ('Installing model...', 98),
        'success': ('Download complete!', 100)
    }

    for key, (status, progress) in status_messages.items():
        if key in line:
            download_progress.update({
                'status': status,
                'progress': progress
            })
            if key == 'success':
                download_progress.update({
                    'downloading': False,
                    'completion_time': time.time()
                })
                logger.info("Model download completed successfully!")
            logger.info(f"Download status: {status}")
            return

    # Process layer download progress
    if 'pulling' in line and '%' in line:
        try:
            # Extract percentage
            percent_match = re.search(r'(\d+)%', line)
            if percent_match:
                progress_percent = int(percent_match.group(1))

                # Scale to 5-90% range to leave room for setup and finalization
                scaled_progress = 5 + int((progress_percent * 0.85))

                # Track the current layer's progress
                if layer_id:
                    if 'layer_progress' not in download_progress:
                        download_progress['layer_progress'] = {}

                    download_progress['layer_progress'][layer_id] = scaled_progress

                    # When a layer hits 100%, mark it as completed
                    if progress_percent >= 99:
                        download_progress['completed_layers'].add(layer_id)

                # Only update if it's an increase (prevents dropping back to 0%)
                if scaled_progress > download_progress['progress']:
                    download_progress['progress'] = scaled_progress
                    logger.debug(f"Updated progress to {scaled_progress}%")

            # Extract size info (e.g., "4.1 GB/4.1 GB")
            size_match = re.search(r'(\d+\.?\d*)\s*([KMGT]?B)/(\d+\.?\d*)\s*([KMGT]?B)', line)
            if size_match:
                completed, completed_unit, total, total_unit = size_match.groups()
                download_progress.update({
                    'completed': f"{completed} {completed_unit}",
                    'total': f"{total} {total_unit}",
                })

            # Extract speed (e.g., "125 MB/s")
            speed_match = re.search(r'(\d+\.?\d*)\s*([KMGT]?B/s)', line)
            if speed_match:
                speed, speed_unit = speed_match.groups()
                download_progress['speed'] = f"{speed} {speed_unit}"

            # Update status with layer info if available
            if layer_id:
                download_progress['status'] = f"Downloading file: {layer_id[:8]}... ({download_progress['progress']}%)"
            else:
                download_progress['status'] = f"Downloading model... ({download_progress['progress']}%)"

        except Exception as e:
            logger.warning(f"Failed to parse download line: {line}, error: {e}")

@app.route('/health', methods=['GET'])
@app.route('/api/model-status', methods=['GET'])
def health_check():
    """Health check endpoint for monitoring the application and LLM status"""
    global model_status_cache, download_progress

    # Use cached response if available and recent
    current_time = time.time()
    if (model_status_cache['response'] is not None and
            current_time - model_status_cache['timestamp'] < model_status_cache['cache_ttl']):
        logger.debug("Returning cached model status response")
        cached_response = model_status_cache['response']
        cached_response.headers['Cache-Control'] = f"public, max-age={model_status_cache['cache_ttl']}"
        return cached_response

    # Track API call counts
    download_progress['api_call_count'] += 1

    try:
        # System information
        system_info = {
            'python_version': platform.python_version(),
            'platform': platform.platform(),
            'cpu_percent': psutil.cpu_percent(interval=0.1),
            'memory_percent': psutil.virtual_memory().percent
        }

        # Check Ollama status
        ollama_status = {
            'running': False,
            'models': [],
            'version': 'unknown'
        }

        is_connected, response = check_ollama_connection()
        if is_connected:
            ollama_status['running'] = True
            models_data = response.json().get('models', [])
            ollama_status['models'] = [model.get('name') for model in models_data]

            # Try to get version
            try:
                version_response = requests.get(get_ollama_url('/api/version'), timeout=1)
                if version_response.status_code == 200:
                    ollama_status['version'] = version_response.json().get('version', 'unknown')
            except Exception as e:
                logger.warning(f"Failed to get Ollama version: {e}")

        # Get model ID from request parameter if present
        model_id = request.args.get('modelId', active_model)
        model_available = is_model_available(model_id)

        # If model is available but we think we're downloading, reset the state
        if model_available and download_progress['downloading']:
            logger.warning(f"Model {model_id} is available but download state shows downloading - fixing state")
            download_progress.update({
                'downloading': False,
                'status': 'Model ready',
                'progress': 100,
                'completion_time': time.time()
            })

        # Determine overall status
        if not ollama_status['running']:
            status = "error"
        elif download_progress['downloading']:
            status = "downloading"
        elif model_available:
            status = "ok"
        elif (download_progress.get('completion_time', 0) > 0 and
              time.time() - download_progress['completion_time'] < 30):
            # Download just completed, give it a moment to be available
            status = "ok"
            logger.info(f"Download completed recently, model {model_id} should be ready")
        else:
            status = "loading"

        # Create response object
        response_data = {
            'status': 'ok',  # Always return 'ok' for the frontend
            'actual_status': status,
            'model': model_id,
            'active_model': active_model,
            'ollama': ollama_status,
            'system': system_info,
            'download_progress': download_progress,
            'timestamp': time.time()
        }

        response = jsonify(response_data)
        response.headers['Cache-Control'] = f"public, max-age={model_status_cache['cache_ttl']}"

        # Cache this response
        model_status_cache['response'] = response
        model_status_cache['timestamp'] = time.time()

        return response

    except Exception as e:
        logger.error(f"Health check error: {e}")
        error_response = jsonify({
            'status': 'ok',  # Still return 'ok' for the frontend
            'actual_status': 'error',
            'error': str(e),
            'download_progress': download_progress,
            'timestamp': time.time()
        })
        return error_response

@app.route('/api/chat', methods=['POST'])
def chat():
    """Process chat messages with file change awareness"""
    try:
        start_time = time.time()
        data = request.get_json()
        message = data.get('message', '').strip()
        project_session = data.get('project_session')

        if not message:
            return jsonify({
                'success': False,
                'error': 'Message is empty'
            })

        # Check if Ollama is running
        is_connected, _ = check_ollama_connection()

        if is_connected:
            try:
                # Create enhanced context with file changes
                enhanced_message = get_enhanced_chat_context(project_session, message)

                # Create a system prompt that's aware of file changes
                system_prompt = """
                You are a Terraform LLM Assistant, specializing in infrastructure as code, 
                Terraform, AWS, and cloud architecture. You now have access to real-time file changes 
                in the user's project.

                When responding:
                - Use a clear, professional tone suitable for technical documentation
                - Be aware of recent file changes and reference them when relevant
                - If you see recent modifications, offer insights about the changes
                - Suggest improvements or point out potential issues with recent edits
                - Always wrap code in triple backticks with the appropriate language specifier
                - Include clear comments in your code examples
                - Focus on security, maintainability, and following cloud best practices

                Pay special attention to:
                - Recent file modifications and their implications
                - Patterns in the changes being made
                - Potential issues or improvements suggested by the edit history
                - Consistency across modified files
                """

                formatted_prompt = f"{system_prompt}\n\n{enhanced_message}\n\nAssistant:"

                # Try streaming first
                full_response = ""
                try:
                    response = requests.post(
                        get_ollama_url('/api/generate'),
                        json={
                            'model': active_model,
                            'prompt': formatted_prompt,
                            'stream': True,
                            'options': {
                                'temperature': 0.1,
                                'top_p': 0.9,
                                'top_k': 40
                            }
                        },
                        stream=True,
                        timeout=120
                    )

                    if response.status_code == 200:
                        for line in response.iter_lines():
                            if not line:
                                continue

                            try:
                                chunk = json.loads(line)
                                if 'response' in chunk:
                                    full_response += chunk['response']
                            except json.JSONDecodeError:
                                logger.warning(f"Could not decode JSON from stream: {line}")

                except Exception as streaming_error:
                    logger.error(f"Error in streaming response: {streaming_error}")
                    # Fallback to non-streaming
                    response = requests.post(
                        get_ollama_url('/api/generate'),
                        json={
                            'model': active_model,
                            'prompt': formatted_prompt,
                            'stream': False,
                            'options': {
                                'temperature': 0.1,
                                'top_p': 0.9,
                                'top_k': 40
                            }
                        },
                        timeout=180
                    )

                if response.status_code == 200:
                    response_time = time.time() - start_time

                    # Handle both streaming and non-streaming responses
                    if full_response:
                        response_text = full_response
                    else:
                        result = response.json()
                        response_text = result.get('response', '')

                    return jsonify({
                        'success': True,
                        'response': response_text,
                        'model': active_model,
                        'response_time': round(response_time, 2),
                        'context_enhanced': bool(project_session)
                    })
                else:
                    logger.error(f"Ollama API returned status code: {response.status_code}")
                    return jsonify({
                        'success': False,
                        'error': f"LLM service returned an error: {response.status_code}",
                        'response_time': round(time.time() - start_time, 2)
                    })

            except Exception as e:
                logger.error(f"Error calling Ollama API: {e}")
                return jsonify({
                    'success': False,
                    'error': f"Error communicating with LLM service: {str(e)}",
                    'response_time': round(time.time() - start_time, 2)
                })

        # Fallback response when Ollama is not available
        return jsonify({
            'success': True,
            'response': (
                "I received your question about infrastructure, but the LLM service is currently unavailable. "
                "Please ensure Ollama is running and the correct model is loaded. "
                f"Expected model: {active_model}"
            ),
            'response_time': round(time.time() - start_time, 2)
        })

    except Exception as e:
        logger.error(f"Error in chat endpoint: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'response_time': 0
        })

@app.route('/api/status-no-download')
def status_no_download():
    """Status check that won't trigger downloads"""
    try:
        is_connected, response = check_ollama_connection(timeout=5)

        if is_connected:
            models = response.json().get('models', [])
            model_names = [m.get('name', '') for m in models]
            model_available = is_model_available(active_model)

            return jsonify({
                'status': 'ready' if model_available else 'model_not_found',
                'model': active_model,
                'available': model_available,
                'models': model_names
            })
        else:
            return jsonify({
                'status': 'error',
                'message': f"Ollama returned error status"
            }), 500

    except requests.exceptions.ConnectionError:
        return jsonify({
            'status': 'not_running',
            'message': "Ollama service is not running"
        }), 503
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/status')
def status():
    """Check status and list available models"""
    try:
        is_connected, response = check_ollama_connection(timeout=5)

        if is_connected:
            models = response.json().get('models', [])
            model_available = is_model_available(active_model)

            if model_available:
                return jsonify({
                    'status': 'ready',
                    'model': active_model,
                    'models': models
                })
            else:
                return jsonify({
                    'status': 'model_not_found',
                    'message': f"Model {active_model} not found",
                    'models': models
                })
        else:
            return jsonify({
                'status': 'error',
                'message': f"Ollama service error"
            }), 500

    except requests.exceptions.ConnectionError:
        return jsonify({
            'status': 'not_running',
            'message': "Ollama service is not running"
        }), 503
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/download-model', methods=['POST'])
def download_model():
    """Endpoint to trigger the download of a model"""
    global download_progress

    try:
        # Check if automatic downloads are disabled
        if AUTO_DOWNLOAD_DISABLED:
            logger.info("Automatic model download request received but downloads are disabled by config")
            return jsonify({
                'success': True,
                'message': "Model downloads are disabled on this server",
                'download_needed': False
            })

        # Get model ID from request
        data = request.get_json() or {}
        model_id = data.get('modelId', active_model)

        # Check if already downloading
        if download_progress['downloading']:
            logger.info(f"Download already in progress for model: {download_progress['model']}")
            return jsonify({
                'success': True,
                'status': 'in_progress',
                'message': f"Already downloading model: {download_progress['model']}",
                'progress_pct': download_progress['progress']
            }), 202

        # Rate limiting
        current_time = time.time()
        last_attempt = download_progress.get('last_download_attempt_time', 0)
        cooldown_seconds = 5

        if current_time - last_attempt < cooldown_seconds:
            retry_after = int(cooldown_seconds - (current_time - last_attempt)) + 1
            logger.warning(f"Download request rate limited - retry after {retry_after} seconds")

            response = jsonify({
                'success': False,
                'status': 'rate_limited',
                'error': 'Too many download requests in quick succession',
                'retry_after_seconds': retry_after
            })
            response.headers['Retry-After'] = str(retry_after)
            return response, 429

        # Update timestamp for rate-limiting
        download_progress['last_download_attempt_time'] = current_time

        # Check if model is already available
        if is_model_available(model_id):
            logger.info(f"Model {model_id} is already available, no need to download")
            download_progress.update({
                'downloading': False,
                'status': 'Available',
                'progress': 100,
                'completion_time': time.time(),
                'download_attempt': download_progress.get('download_attempt', 0) + 1
            })

            return jsonify({
                'success': True,
                'status': 'ready',
                'message': f"Model {model_id} is already available",
                'download_needed': False
            })

        # Check if Ollama is available
        is_connected, _ = check_ollama_connection()
        if not is_connected:
            return jsonify({
                'success': False,
                'error': 'Ollama service is not available'
            })

        # Reset and start download progress tracking
        download_progress.update({
            'downloading': True,
            'model': model_id,
            'progress': 0,
            'status': 'Starting download...',
            'total': 0,
            'completed': 0,
            'speed': '',
            'eta': '',
            'completed_layers': set(),
            'layer_progress': {},
            'current_layer': None
        })

        def download_with_progress():
            """Download model with progress tracking in background thread"""
            try:
                logger.info(f"Preparing to download model: {model_id}")
                download_progress['status'] = "Starting download..."
                download_progress['progress'] = 1

                # Start the ollama pull process
                process = subprocess.Popen(
                    ["ollama", "pull", model_id],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    universal_newlines=True,
                    bufsize=1
                )

                logger.info(f"Started download process for model: {model_id}")

                # Track time for stall detection
                last_update_time = time.time()
                last_progress = 0

                # Read output line by line to track progress
                for line in iter(process.stdout.readline, ''):
                    if line:
                        parse_download_line(line)

                        # Update time if progress changed
                        if download_progress['progress'] != last_progress:
                            last_update_time = time.time()
                            last_progress = download_progress['progress']

                        # Check for stalled download
                        if time.time() - last_update_time > 60:
                            logger.warning("Download appears to be stalled - no progress for 60 seconds")
                            download_progress['status'] = f"Download may be stalled... ({download_progress['progress']}%)"

                # Wait for process to complete
                try:
                    exit_code = process.wait(timeout=300)  # 5 minute timeout

                    if exit_code == 0:
                        download_progress.update({
                            'downloading': False,
                            'status': 'Download complete!',
                            'progress': 100,
                            'completion_time': time.time(),
                            'download_attempt': download_progress.get('download_attempt', 0) + 1
                        })

                        # Convert set to list for JSON serialization
                        if isinstance(download_progress['completed_layers'], set):
                            download_progress['completed_layers'] = list(download_progress['completed_layers'])

                        logger.info(f"Successfully downloaded model: {model_id}")

                        # Brief wait for model to become available
                        time.sleep(3)

                        # Clear the download state after successful completion
                        download_progress.update({
                            'downloading': False,
                            'status': 'Model ready',
                            'progress': 100
                        })

                        # Verify model availability
                        if is_model_available(model_id):
                            logger.info(f"Model {model_id} is now available and ready")
                        else:
                            logger.warning(f"Model {model_id} download completed but not yet available")
                            # Give it a bit more time
                            time.sleep(2)
                            if is_model_available(model_id):
                                logger.info(f"Model {model_id} is now available after additional wait")
                    else:
                        download_progress.update({
                            'downloading': False,
                            'status': f'Download failed with exit code {exit_code}',
                            'progress': 0
                        })
                        logger.error(f"Failed to download model: {model_id}, exit code: {exit_code}")

                except subprocess.TimeoutExpired:
                    process.kill()
                    download_progress.update({
                        'downloading': False,
                        'status': 'Download timeout after 5 minutes of no activity',
                        'progress': 0
                    })
                    logger.error(f"Download process timeout: {model_id}")

            except Exception as e:
                download_progress.update({
                    'downloading': False,
                    'status': f'Error: {str(e)}',
                    'progress': 0
                })
                logger.error(f"Download process error: {e}")

        # Start download in background thread
        thread = threading.Thread(target=download_with_progress, daemon=True)
        thread.start()

        return jsonify({
            'success': True,
            'message': f"Started downloading model: {model_id}"
        })

    except Exception as e:
        logger.error(f"Error in download model endpoint: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/api/reset-download-state', methods=['POST'])
def reset_download_state():
    """Reset download state if model is actually available"""
    global download_progress

    try:
        # Check if the active model is actually available
        if is_model_available(active_model):
            logger.info(f"Model {active_model} is available, resetting download state")
            download_progress.update({
                'downloading': False,
                'status': 'Model ready',
                'progress': 100,
                'completion_time': time.time()
            })
            return jsonify({
                'success': True,
                'message': f'Reset download state - model {active_model} is available'
            })
        else:
            return jsonify({
                'success': False,
                'message': f'Model {active_model} is not available'
            })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/api/debug-status')
def debug_status():
    """Debug endpoint to see detailed status information"""
    try:
        is_connected, response = check_ollama_connection()
        available_models = get_available_models()
        model_available = is_model_available(active_model)

        debug_info = {
            'ollama_connected': is_connected,
            'active_model': active_model,
            'available_models': available_models,
            'model_available': model_available,
            'download_progress': download_progress,
            'current_time': time.time()
        }

        return jsonify(debug_info)
    except Exception as e:
        return jsonify({'error': str(e)})

# Run the application
if __name__ == '__main__':
    host = os.environ.get('HOST', '0.0.0.0')
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'

    logger.info(f"Starting server on {host}:{port} (debug={debug})")
    app.run(host=host, port=port, debug=debug)