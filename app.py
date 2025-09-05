import os
import json
import uuid
import shutil
import hashlib
import logging
import zipfile
import tarfile
import tempfile
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

import requests
from flask import Flask, render_template, request, jsonify, send_from_directory

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration constants
UPLOAD_FOLDER = 'uploads'
MAX_CONTENT_LENGTH = 500 * 1024 * 1024  # 500MB
ALLOWED_EXTENSIONS = {
    'zip', 'tar', 'gz', 'bz2', 'xz', 'tar.gz', 'tar.bz2', 'tar.xz',
    'py', 'js', 'html', 'css', 'json', 'txt', 'md', 'yml', 'yaml'
}

# Project structure patterns for VS Code and IntelliJ
PROJECT_INDICATORS = {
    'python': ['requirements.txt', 'setup.py', 'pyproject.toml', 'Pipfile'],
    'javascript': ['package.json', 'yarn.lock', 'package-lock.json'],
    'java': ['pom.xml', 'build.gradle', 'build.xml'],
    'docker': ['Dockerfile', 'docker-compose.yml', 'docker-compose.yaml'],
    'terraform': ['main.tf', '*.tf'],
    'kubernetes': ['*.yaml', '*.yml'],
}

# Global variables
app = None
secret_key = None
active_model = None
ollama_host = 'localhost'
ollama_port = 11434
AUTO_DOWNLOAD_DISABLED = False
file_tracker = None
download_progress = {}
model_status_cache = {}
TERRAFORM_SANDBOX_URL = None
host = None
port = None
debug = None


class FileChangeTracker:
    """Tracks file changes and maintains change history for projects."""
    
    def __init__(self):
        self.project_changes: Dict[str, List[Dict]] = {}
        self.file_hashes: Dict[str, str] = {}

    def initialize_project(self, project_id: str, project_path: str) -> None:
        """Initialize tracking for a new project."""
        self.project_changes[project_id] = []
        
        # Generate initial hashes for all files
        for root, dirs, files in os.walk(project_path):
            for file in files:
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, 'rb') as f:
                        content = f.read()
                        file_hash = hashlib.sha256(content).hexdigest()
                        relative_path = os.path.relpath(file_path, project_path)
                        hash_key = f"{project_id}:{relative_path}"
                        self.file_hashes[hash_key] = file_hash
                except (IOError, OSError) as e:
                    logger.warning(f"Could not read file {file_path}: {e}")

    def track_file_change(self, project_id: str, file_path: str, 
                         content: bytes, operation: str = 'update') -> None:
        """Track changes to a file."""
        try:
            relative_path = file_path
            if file_path.startswith('/'):
                relative_path = file_path[1:]

            hash_key = f"{project_id}:{relative_path}"
            new_hash = hashlib.sha256(content).hexdigest()
            old_hash = self.file_hashes.get(hash_key)

            if old_hash != new_hash or operation in ['create', 'delete']:
                change_entry = {
                    'timestamp': datetime.now().isoformat(),
                    'file_path': relative_path,
                    'operation': operation,
                    'old_hash': old_hash,
                    'new_hash': new_hash if operation != 'delete' else None,
                    'diff_summary': self._generate_diff_summary(
                        old_hash, new_hash, relative_path, content, operation
                    )
                }

                if project_id not in self.project_changes:
                    self.project_changes[project_id] = []
                
                self.project_changes[project_id].append(change_entry)
                
                # Keep only last 100 changes per project
                if len(self.project_changes[project_id]) > 100:
                    self.project_changes[project_id] = self.project_changes[project_id][-100:]

                # Update hash
                if operation != 'delete':
                    self.file_hashes[hash_key] = new_hash
                else:
                    self.file_hashes.pop(hash_key, None)

        except Exception as e:
            logger.error(f"Error tracking file change: {e}")

    def _generate_diff_summary(self, old_hash: str, new_hash: str, 
                              file_path: str, content: bytes, operation: str) -> str:
        """Generate a summary of changes made to a file."""
        try:
            if operation == 'create':
                return f"Created new file with {len(content)} bytes"
            elif operation == 'delete':
                return "File deleted"
            elif operation == 'update':
                if old_hash == new_hash:
                    return "No changes detected"
                
                # Try to decode content for text files
                try:
                    text_content = content.decode('utf-8')
                    lines = len(text_content.split('\n'))
                    chars = len(text_content)
                    return f"Updated file: {lines} lines, {chars} characters"
                except UnicodeDecodeError:
                    return f"Updated binary file: {len(content)} bytes"
            
            return f"Operation: {operation}"
        except Exception as e:
            logger.error(f"Error generating diff summary: {e}")
            return f"Operation: {operation} (error generating summary)"

    def get_recent_changes(self, project_id: str, limit: int = 20) -> List[Dict]:
        """Get recent changes for a project."""
        if project_id not in self.project_changes:
            return []
        
        changes = self.project_changes[project_id]
        return sorted(changes, key=lambda x: x['timestamp'], reverse=True)[:limit]

    def get_project_change_summary(self, project_id: str) -> Dict[str, Any]:
        """Get a summary of all changes for a project."""
        if project_id not in self.project_changes:
            return {
                'total_changes': 0,
                'files_modified': 0,
                'last_change': None,
                'operations': {}
            }

        changes = self.project_changes[project_id]
        files_modified = set()
        operations = {}
        
        for change in changes:
            files_modified.add(change['file_path'])
            op = change['operation']
            operations[op] = operations.get(op, 0) + 1

        return {
            'total_changes': len(changes),
            'files_modified': len(files_modified),
            'last_change': changes[-1]['timestamp'] if changes else None,
            'operations': operations
        }


def get_ollama_url() -> str:
    """Get the Ollama URL based on configuration."""
    return f"http://{ollama_host}:{ollama_port}"


def check_ollama_connection() -> bool:
    """Check if Ollama service is available."""
    try:
        response = requests.get(f"{get_ollama_url()}/api/tags", timeout=5)
        return response.status_code == 200
    except requests.exceptions.RequestException as e:
        logger.warning(f"Ollama connection failed: {e}")
        return False


def get_available_models() -> List[str]:
    """Get list of available models from Ollama."""
    try:
        if not check_ollama_connection():
            return []
            
        response = requests.get(f"{get_ollama_url()}/api/tags", timeout=10)
        if response.status_code == 200:
            data = response.json()
            return [model['name'] for model in data.get('models', [])]
        return []
    except Exception as e:
        logger.error(f"Error fetching models: {e}")
        return []


def is_model_available(model_name: str) -> bool:
    """Check if a specific model is available."""
    try:
        available_models = get_available_models()
        return any(model_name in model for model in available_models)
    except Exception as e:
        logger.error(f"Error checking model availability: {e}")
        return False


def allowed_file(filename: str) -> bool:
    """Check if file extension is allowed."""
    if not filename:
        return False
    
    # Handle compound extensions like .tar.gz
    for ext in ALLOWED_EXTENSIONS:
        if filename.lower().endswith(f'.{ext}'):
            return True
    return False


def extract_archive(file_path: str, extract_to: str) -> bool:
    """Extract various archive formats."""
    try:
        if file_path.endswith('.zip'):
            with zipfile.ZipFile(file_path, 'r') as zip_ref:
                zip_ref.extractall(extract_to)
        elif file_path.endswith(('.tar', '.tar.gz', '.tgz', '.tar.bz2', '.tar.xz')):
            with tarfile.open(file_path, 'r:*') as tar_ref:
                tar_ref.extractall(extract_to)
        else:
            return False
        return True
    except Exception as e:
        logger.error(f"Error extracting archive {file_path}: {e}")
        return False


def analyze_project_structure(project_path: str) -> Dict[str, Any]:
    """Analyze project structure and detect project type."""
    analysis = {
        'project_type': 'unknown',
        'detected_technologies': [],
        'file_count': 0,
        'directory_count': 0,
        'main_files': [],
        'configuration_files': [],
        'source_directories': [],
        'total_size': 0
    }

    try:
        for root, dirs, files in os.walk(project_path):
            analysis['directory_count'] += len(dirs)
            analysis['file_count'] += len(files)
            
            for file in files:
                file_path = os.path.join(root, file)
                try:
                    file_size = os.path.getsize(file_path)
                    analysis['total_size'] += file_size
                except OSError:
                    continue
                
                # Check for project indicators
                for tech, indicators in PROJECT_INDICATORS.items():
                    for indicator in indicators:
                        if indicator.startswith('*.'):
                            pattern = indicator[2:]  # Remove '*.'
                            if file.endswith(f'.{pattern}'):
                                if tech not in analysis['detected_technologies']:
                                    analysis['detected_technologies'].append(tech)
                                if analysis['project_type'] == 'unknown':
                                    analysis['project_type'] = tech
                        elif file == indicator:
                            if tech not in analysis['detected_technologies']:
                                analysis['detected_technologies'].append(tech)
                            if analysis['project_type'] == 'unknown':
                                analysis['project_type'] = tech

                            analysis['configuration_files'].append(
                                os.path.relpath(file_path, project_path)
                            )
                
                # Identify main files
                if file in ['main.py', 'app.py', 'index.js', 'main.js', 'index.html']:
                    analysis['main_files'].append(
                        os.path.relpath(file_path, project_path)
                    )

            # Identify source directories
            dir_name = os.path.basename(root)
            if dir_name in ['src', 'source', 'app', 'lib', 'libs', 'components']:
    # Create structure tree
                analysis['source_directories'].append(
                    os.path.relpath(root, project_path)
                )

    except Exception as e:
        logger.error(f"Error analyzing project structure: {e}")

    return analysis


def create_file_tree(path: str, max_depth: int = 3) -> Dict[str, Any]:
    """Create a file tree structure."""
    def _build_tree(current_path: str, current_depth: int = 0) -> Dict[str, Any]:
        if current_depth > max_depth:
            return {'type': 'directory', 'truncated': True}

        try:
            if os.path.isfile(current_path):
                return {'type': 'file', 'size': os.path.getsize(current_path)}
            
            tree = {'type': 'directory', 'children': {}}
            try:
                items = os.listdir(current_path)
                for item in sorted(items):
                    item_path = os.path.join(current_path, item)
                    tree['children'][item] = _build_tree(item_path, current_depth + 1)
            except PermissionError:
                tree['error'] = 'Permission denied'
            
            return tree
        except Exception as e:
            return {'type': 'error', 'message': str(e)}

    return _build_tree(path)


def generate_recommendations(analysis: Dict[str, Any]) -> List[str]:
    """Generate recommendations based on project analysis."""
    recommendations = []

    # General recommendations
    if analysis['file_count'] > 1000:
        recommendations.append(
            "Large project detected. Consider focusing analysis on specific modules."
        )

    # Technology-specific recommendations
    project_type = analysis.get('project_type', 'unknown')
    
    if project_type == 'python':
        if 'requirements.txt' not in [os.path.basename(f) for f in analysis['configuration_files']]:
            recommendations.append(
                "Consider adding a requirements.txt file to track dependencies."
            )
        
        if not any('test' in f.lower() for f in analysis['source_directories']):
            recommendations.append(
                "Consider adding a tests directory for unit tests."
            )

    elif project_type == 'javascript':
        if 'package.json' in [os.path.basename(f) for f in analysis['configuration_files']]:
            recommendations.append(
                "JavaScript/Node.js project detected. Check package.json for scripts and dependencies."
            )

    elif project_type == 'docker':
        recommendations.append(
            "Docker configuration detected. Review Dockerfile and docker-compose files."
        )

    # Security recommendations
    if analysis['total_size'] > 100 * 1024 * 1024:  # 100MB
        recommendations.append(
            "Large project size. Ensure no sensitive files or large binaries are included."
        )

    return recommendations


def read_file_content(file_path: str, max_size: int = 1024 * 1024) -> Dict[str, Any]:
    """Read file content with size and encoding detection."""
    try:
        file_stat = os.stat(file_path)
        file_size = file_stat.st_size
        
        if file_size > max_size:
            return {
                'error': f'File too large ({file_size} bytes). Maximum size: {max_size} bytes',
                'size': file_size
            }

        # Try to read as text first
        encodings = ['utf-8', 'latin-1', 'cp1252']
        content = None
        encoding_used = None
        
        for encoding in encodings:
            try:
                with open(file_path, 'r', encoding=encoding) as f:
                    content = f.read()
                    encoding_used = encoding
                    break
            except UnicodeDecodeError:
                continue

        if content is None:
            # Try binary read
            with open(file_path, 'rb') as f:
                binary_content = f.read()
                return {
                    'content': None,
                    'binary': True,
                    'size': len(binary_content),
                    'error': 'Binary file - content not displayable'
                }

        return {
            'content': content,
            'binary': False,
            'size': file_size,
            'encoding': encoding_used,
            'lines': len(content.split('\n')) if content else 0
        }

    except Exception as e:
        return {'error': f'Error reading file: {str(e)}'}


def initialize_project_tracking(project_id: str, project_path: str) -> None:
    """Initialize project tracking."""
    global file_tracker
    if file_tracker is None:
        file_tracker = FileChangeTracker()
    
    try:
        file_tracker.initialize_project(project_id, project_path)
        logger.info(f"Initialized tracking for project {project_id}")
    except Exception as e:
        logger.error(f"Error initializing project tracking: {e}")


def track_and_update_file(project_id: str, file_path: str, content: bytes, 
                         operation: str = 'update') -> None:
    """Track file changes and update file tracker."""
    global file_tracker
    if file_tracker is None:
        file_tracker = FileChangeTracker()
    
    try:
        file_tracker.track_file_change(project_id, file_path, content, operation)
        logger.debug(f"Tracked {operation} for {file_path} in project {project_id}")
    except Exception as e:
        logger.error(f"Error tracking file change: {e}")


def get_enhanced_chat_context(project_id: str) -> Dict[str, Any]:
    """Get enhanced context for chat based on project changes and analysis."""
    context = {
        'project_id': project_id,
        'recent_changes': [],
        'change_summary': {},
        'project_analysis': None
    }

    global file_tracker
    if file_tracker is not None:
        try:
            # Get recent changes
            context['recent_changes'] = file_tracker.get_recent_changes(project_id, 10)
            
            # Get change summary
            context['change_summary'] = file_tracker.get_project_change_summary(project_id)
            
            # Add project analysis if available
            project_path = os.path.join(UPLOAD_FOLDER, project_id)
            if os.path.exists(project_path):
                context['project_analysis'] = analyze_project_structure(project_path)
                
        except Exception as e:
            logger.error(f"Error getting enhanced chat context: {e}")

    return context


# Flask routes
@app.route('/')
def index():
    """Main index page."""
    return render_template('index.html')


@app.route('/file-browser')
def file_browser():
    """File browser page."""
    return render_template('file_browser.html')


@app.route('/static/<path:filename>')
def serve_static(filename):
    """Serve static files."""
    return send_from_directory('static', filename)


@app.route('/api/download-progress')
def get_download_progress():
    """Get download progress for active downloads."""
    global download_progress
    return jsonify(download_progress)


@app.route('/api/upload', methods=['POST'])
def upload_project():
    """Handle project uploads."""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400

        file = request.files['file']
        if not file or file.filename == '':
            return jsonify({'error': 'No file selected'}), 400

        if not allowed_file(file.filename):
            return jsonify({
                'error': f'File type not allowed. Allowed types: {", ".join(ALLOWED_EXTENSIONS)}'
            }), 400

        # Create unique project ID
        # Create temporary directory for this upload session
        project_id = str(uuid.uuid4())
        project_dir = os.path.join(UPLOAD_FOLDER, project_id)
        os.makedirs(project_dir, exist_ok=True)

        # Save uploaded file
        file_path = os.path.join(project_dir, file.filename)
        file.save(file_path)

        # Extract if it's an archive
        extracted = False
        if file.filename.lower().endswith(('.zip', '.tar', '.tar.gz', '.tgz', '.tar.bz2', '.tar.xz')):
            extract_dir = os.path.join(project_dir, 'extracted')
            os.makedirs(extract_dir, exist_ok=True)
            
            if extract_archive(file_path, extract_dir):
                extracted = True
                # Remove the archive file after successful extraction
                os.remove(file_path)
                # Move extracted contents up one level if there's a single top-level directory
                extracted_items = os.listdir(extract_dir)
                if len(extracted_items) == 1 and os.path.isdir(os.path.join(extract_dir, extracted_items[0])):
                    single_dir = os.path.join(extract_dir, extracted_items[0])
                    temp_dir = os.path.join(project_dir, 'temp')
                    shutil.move(single_dir, temp_dir)
                    shutil.rmtree(extract_dir)
                    shutil.move(temp_dir, extract_dir)
                
                # Use extracted directory as project root
                project_root = extract_dir
            else:
                return jsonify({'error': 'Failed to extract archive'}), 400
        else:
            project_root = project_dir

        # Analyze project structure
        analysis = analyze_project_structure(project_root)
        
        # Initialize project tracking
        initialize_project_tracking(project_id, project_root)
        
        # Generate recommendations
        recommendations = generate_recommendations(analysis)

        return jsonify({
            'success': True,
            'project_id': project_id,
            'filename': file.filename,
            'extracted': extracted,
            'analysis': analysis,
            'recommendations': recommendations
        })

    except Exception as e:
        logger.error(f"Upload error: {e}")
        return jsonify({'error': f'Upload failed: {str(e)}'}), 500


@app.route('/api/projects/<project_id>/files')
def get_project_files(project_id: str):
    """Get project file structure."""
    try:
        project_dir = os.path.join(UPLOAD_FOLDER, project_id)
        
        if not os.path.exists(project_dir):
            return jsonify({'error': 'Project not found'}), 404

        # Check if project was extracted
        extracted_dir = os.path.join(project_dir, 'extracted')
        if os.path.exists(extracted_dir):
            project_root = extracted_dir
        else:
            project_root = project_dir

        # Get file tree
        file_tree = create_file_tree(project_root)
        
        # Get basic stats
        total_files = 0
        total_size = 0
        
        for root, dirs, files in os.walk(project_root):
            total_files += len(files)
            for file in files:
                try:
                    file_path = os.path.join(root, file)
                    total_size += os.path.getsize(file_path)
                except OSError:
                    continue

        return jsonify({
            'project_id': project_id,
            'file_tree': file_tree,
            'stats': {
                'total_files': total_files,
                'total_size': total_size
            }
        })

    except Exception as e:
        logger.error(f"Error getting project files: {e}")
        return jsonify({'error': f'Failed to get project files: {str(e)}'}), 500


@app.route('/api/projects/<project_id>/files/<path:file_path>')
def get_file_content(project_id: str, file_path: str):
    """Get content of a specific file."""
    try:
        project_dir = os.path.join(UPLOAD_FOLDER, project_id)
        
        if not os.path.exists(project_dir):
            return jsonify({'error': 'Project not found'}), 404

        # Check if project was extracted
        extracted_dir = os.path.join(project_dir, 'extracted')
        if os.path.exists(extracted_dir):
            project_root = extracted_dir
        else:
            project_root = project_dir

        # Construct full file path
        full_file_path = os.path.join(project_root, file_path)
        
        # Security check - ensure file is within project directory
        if not full_file_path.startswith(os.path.abspath(project_root)):
            return jsonify({'error': 'Invalid file path'}), 400

        if not os.path.exists(full_file_path):
            return jsonify({'error': 'File not found'}), 404

        if not os.path.isfile(full_file_path):
            return jsonify({'error': 'Path is not a file'}), 400

        # Read file content
        file_info = read_file_content(full_file_path)
        
        return jsonify({
            'project_id': project_id,
            'file_path': file_path,
            'file_info': file_info
        })

    except Exception as e:
        logger.error(f"Error getting file content: {e}")
        return jsonify({'error': f'Failed to get file content: {str(e)}'}), 500


@app.route('/api/projects/<project_id>/files/<path:file_path>', methods=['PUT'])
def update_file_content(project_id: str, file_path: str):
    """Update content of a specific file."""
    try:
        project_dir = os.path.join(UPLOAD_FOLDER, project_id)
        
        if not os.path.exists(project_dir):
            return jsonify({'error': 'Project not found'}), 404

        # Check if project was extracted
        extracted_dir = os.path.join(project_dir, 'extracted')
        if os.path.exists(extracted_dir):
            project_root = extracted_dir
        else:
            project_root = project_dir

        # Get content from request
        data = request.get_json()
        if not data or 'content' not in data:
            return jsonify({'error': 'No content provided'}), 400

        content = data['content']
        
        # Construct full file path
        full_file_path = os.path.join(project_root, file_path)
        
        # Security check
        # Security check - ensure file is within project directory
        if not full_file_path.startswith(os.path.abspath(project_root)):
            return jsonify({'error': 'Invalid file path'}), 400

        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(full_file_path), exist_ok=True)

        # Write content to file
        with open(full_file_path, 'w', encoding='utf-8') as f:
            f.write(content)

        # Track the change
        track_and_update_file(
            project_id, 
            file_path, 
            content.encode('utf-8'), 
            'update' if os.path.exists(full_file_path) else 'create'
        )

        return jsonify({
            'success': True,
            'project_id': project_id,
            'file_path': file_path,
            'message': 'File updated successfully'
        })

    except Exception as e:
        logger.error(f"Error updating file: {e}")
        return jsonify({'error': f'Failed to update file: {str(e)}'}), 500


@app.route('/api/projects/<project_id>/files/<path:file_path>', methods=['DELETE'])
def delete_file(project_id: str, file_path: str):
    """Delete a specific file."""
    try:
        project_dir = os.path.join(UPLOAD_FOLDER, project_id)
        
        if not os.path.exists(project_dir):
            return jsonify({'error': 'Project not found'}), 404

        # Check if project was extracted
        extracted_dir = os.path.join(project_dir, 'extracted')
        if os.path.exists(extracted_dir):
            project_root = extracted_dir
        else:
            project_root = project_dir

        # Construct full file path
        full_file_path = os.path.join(project_root, file_path)
        
        # Security check
        # Security check - ensure file is within project directory
        if not full_file_path.startswith(os.path.abspath(project_root)):
            return jsonify({'error': 'Invalid file path'}), 400

        if not os.path.exists(full_file_path):
            return jsonify({'error': 'File not found'}), 404

        # Read content before deletion for tracking
        if os.path.isfile(full_file_path):
            try:
                with open(full_file_path, 'rb') as f:
                    content = f.read()
                
                # Track the deletion
                track_and_update_file(project_id, file_path, content, 'delete')
            except Exception as e:
                logger.warning(f"Could not read file for tracking before deletion: {e}")

        # Delete file or directory
        if os.path.isfile(full_file_path):
            os.remove(full_file_path)
        elif os.path.isdir(full_file_path):
            shutil.rmtree(full_file_path)

        return jsonify({
            'success': True,
            'project_id': project_id,
            'file_path': file_path,
            'message': 'File deleted successfully'
        })

    except Exception as e:
        logger.error(f"Error deleting file: {e}")
        return jsonify({'error': f'Failed to delete file: {str(e)}'}), 500


@app.route('/api/projects/<project_id>/files', methods=['POST'])
def create_new_file(project_id: str):
    """Create a new file or directory."""
    try:
        project_dir = os.path.join(UPLOAD_FOLDER, project_id)
        
        if not os.path.exists(project_dir):
            return jsonify({'error': 'Project not found'}), 404

        # Check if project was extracted
        extracted_dir = os.path.join(project_dir, 'extracted')
        if os.path.exists(extracted_dir):
            project_root = extracted_dir
        else:
            project_root = project_dir

        # Get request data
        data = request.get_json()
        if not data or 'path' not in data:
            return jsonify({'error': 'No path provided'}), 400

        file_path = data['path']
        content = data.get('content', '')
        is_directory = data.get('is_directory', False)

        # Construct full file path
        full_file_path = os.path.join(project_root, file_path)
        
        # Security check
        # Security check - ensure file is within project directory
        if not full_file_path.startswith(os.path.abspath(project_root)):
            return jsonify({'error': 'Invalid file path'}), 400

        # Check if file already exists
        if os.path.exists(full_file_path):
            return jsonify({'error': 'File or directory already exists'}), 409

        if is_directory:
            # Create directory
            os.makedirs(full_file_path, exist_ok=True)
            message = 'Directory created successfully'
        else:
            # Create directory structure if needed
            os.makedirs(os.path.dirname(full_file_path), exist_ok=True)
            
            # Create file
            with open(full_file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            # Track the creation
            track_and_update_file(project_id, file_path, content.encode('utf-8'), 'create')
            message = 'File created successfully'

        return jsonify({
            'success': True,
            'project_id': project_id,
            'file_path': file_path,
            'is_directory': is_directory,
            'message': message
        })

    except Exception as e:
        logger.error(f"Error creating file: {e}")
        return jsonify({'error': f'Failed to create file: {str(e)}'}), 500


@app.route('/api/projects/<project_id>/changes')
def get_project_changes(project_id: str):
    """Get recent changes for a project."""
    try:
        global file_tracker
        if file_tracker is None:
            return jsonify({'changes': [], 'summary': {}})

        recent_changes = file_tracker.get_recent_changes(project_id, 50)
        change_summary = file_tracker.get_project_change_summary(project_id)

        return jsonify({
            'project_id': project_id,
            'changes': recent_changes,
            'summary': change_summary
        })

    except Exception as e:
        logger.error(f"Error getting project changes: {e}")
        return jsonify({'error': f'Failed to get changes: {str(e)}'}), 500


@app.route('/api/projects/<project_id>/changes', methods=['DELETE'])
def clear_project_changes(project_id: str):
    """Clear change history for a project."""
    try:
        global file_tracker
        if file_tracker is not None and project_id in file_tracker.project_changes:
            file_tracker.project_changes[project_id] = []

        return jsonify({
            'success': True,
            'project_id': project_id,
            'message': 'Change history cleared'
        })

    except Exception as e:
        logger.error(f"Error clearing project changes: {e}")
        return jsonify({'error': f'Failed to clear changes: {str(e)}'}), 500


@app.route('/api/analyze', methods=['POST'])
def analyze_project_with_llm():
    """Analyze project using LLM."""
    try:
        data = request.get_json()
        project_id = data.get('project_id')
        analysis_type = data.get('analysis_type', 'general')
        specific_files = data.get('files', [])

        if not project_id:
            return jsonify({'error': 'Project ID required'}), 400

        project_dir = os.path.join(UPLOAD_FOLDER, project_id)
        if not os.path.exists(project_dir):
            return jsonify({'error': 'Project not found'}), 404

        # Check if project was extracted
        extracted_dir = os.path.join(project_dir, 'extracted')
        if os.path.exists(extracted_dir):
            project_root = extracted_dir
        else:
            project_root = project_dir

        # Get project analysis
        analysis = analyze_project_structure(project_root)
        
        # Prepare context for LLM
        context = {
            'project_analysis': analysis,

            'analysis_type': analysis_type,
            'specific_files': []
        }

        # Read specific files if requested
        if specific_files:
            for file_path in specific_files[:10]:  # Limit to 10 files
                full_path = os.path.join(project_root, file_path)
                if os.path.exists(full_path) and os.path.isfile(full_path):
                    file_info = read_file_content(full_path, max_size=50000)  # 50KB limit
                    if not file_info.get('error') and not file_info.get('binary'):
                        context['specific_files'].append({
                            'path': file_path,
                            'content': file_info['content'][:10000],  # Further limit content
                            'size': file_info['size'],
                            'lines': file_info.get('lines', 0)
                        })

        # Get enhanced context with recent changes
        enhanced_context = get_enhanced_chat_context(project_id)
        context['recent_changes'] = enhanced_context['recent_changes'][:5]  # Last 5 changes

        # Prepare prompt based on analysis type
        if analysis_type == 'security':
            prompt = f"""
            Analyze this project for security issues:
            
            Project Type: {analysis['project_type']}
            Technologies: {', '.join(analysis['detected_technologies'])}
            File Count: {analysis['file_count']}
            
            Configuration files: {', '.join(analysis['configuration_files'])}
            
            Please identify potential security vulnerabilities, insecure configurations, 
            and provide recommendations for improving security.
            """
        elif analysis_type == 'structure':
            prompt = f"""
            Analyze the structure and organization of this project:
            
            Project Type: {analysis['project_type']}
            Technologies: {', '.join(analysis['detected_technologies'])}
            File Count: {analysis['file_count']}
            Directory Count: {analysis['directory_count']}
            
            Main files: {', '.join(analysis['main_files'])}
            Source directories: {', '.join(analysis['source_directories'])}
            
            Please provide feedback on project organization, structure improvements,
            and best practices for this type of project.
            """
        elif analysis_type == 'dependencies':
            prompt = f"""
            Analyze the dependencies and configuration of this project:
            
            Project Type: {analysis['project_type']}
            Technologies: {', '.join(analysis['detected_technologies'])}
            
            Configuration files found: {', '.join(analysis['configuration_files'])}
            
            Please analyze dependencies, identify potential issues, outdated packages,
            and suggest improvements.
            """
        else:  # general
            prompt = f"""
            Provide a general analysis of this project:
            
            Project Type: {analysis['project_type']}
            Technologies: {', '.join(analysis['detected_technologies'])}
            File Count: {analysis['file_count']}
            Total Size: {analysis['total_size']} bytes
            
            Main files: {', '.join(analysis['main_files'])}
            Configuration files: {', '.join(analysis['configuration_files'])}
            
            Please provide an overview, identify the project purpose, 
            highlight key components, and suggest improvements.
            """

        # Add specific file content if available
        if context['specific_files']:
            prompt += "\n\nKey files content (limited):\n"
            for file_info in context['specific_files']:
                prompt += f"\n--- {file_info['path']} ---\n"
                prompt += file_info['content'][:2000]  # Limit content
                if len(file_info['content']) > 2000:
                    prompt += "\n... (content truncated)"

        # Add recent changes context
        if context['recent_changes']:
            prompt += "\n\nRecent changes:\n"
            for change in context['recent_changes']:
                prompt += f"- {change['operation']} {change['file_path']} ({change['timestamp']})\n"

        # Call LLM (this would be implemented based on your LLM integration)
        # For now, return the analysis structure
        return jsonify({
            'success': True,
            'project_id': project_id,
            'analysis_type': analysis_type,
            'context': context,
            'prompt': prompt,
            'message': 'Analysis prepared (LLM integration needed)'
        })

    except Exception as e:
        logger.error(f"Error in project analysis: {e}")
        return jsonify({'error': f'Analysis failed: {str(e)}'}), 500


@app.route('/api/cleanup/<project_id>', methods=['DELETE'])
def cleanup_project(project_id: str):
    """Clean up project files."""
    try:
        project_dir = os.path.join(UPLOAD_FOLDER, project_id)
        
        if os.path.exists(project_dir):
            shutil.rmtree(project_dir)

        # Clean up tracking data
        global file_tracker
        if file_tracker is not None:
            if project_id in file_tracker.project_changes:
                del file_tracker.project_changes[project_id]
            
            # Clean up file hashes
            keys_to_remove = [k for k in file_tracker.file_hashes.keys() if k.startswith(f"{project_id}:")]
            for key in keys_to_remove:
                del file_tracker.file_hashes[key]

        return jsonify({
            'success': True,
            'project_id': project_id,
            'message': 'Project cleaned up successfully'
        })

    except Exception as e:
        logger.error(f"Error cleaning up project: {e}")
        return jsonify({'error': f'Cleanup failed: {str(e)}'}), 500


@app.route('/api/projects')
def list_projects():
    """List all available projects."""
    try:
        projects = []
        
        if not os.path.exists(UPLOAD_FOLDER):
            return jsonify({'projects': projects})

        for item in os.listdir(UPLOAD_FOLDER):
            project_path = os.path.join(UPLOAD_FOLDER, item)
            if os.path.isdir(project_path):
                try:
                    # Get project info
                    project_info = {
                        'id': item,
                        'created': datetime.fromtimestamp(
                            os.path.getctime(project_path)
                        ).isoformat(),
                        'size': 0,
                        'file_count': 0
                    }

                    # Calculate size and file count
                    for root, dirs, files in os.walk(project_path):
                        project_info['file_count'] += len(files)
                        for file in files:
                            try:
                                file_path = os.path.join(root, file)
                                project_info['size'] += os.path.getsize(file_path)
                            except OSError:
                                continue

                    # Get project analysis if available
                    extracted_dir = os.path.join(project_path, 'extracted')
                    if os.path.exists(extracted_dir):
                        analysis = analyze_project_structure(extracted_dir)
                        project_info.update({
                            'project_type': analysis['project_type'],
                            'technologies': analysis['detected_technologies']
                        })

                    projects.append(project_info)

                except Exception as e:
                    logger.warning(f"Error getting info for project {item}: {e}")
                    continue

        # Sort by creation time (newest first)
        projects.sort(key=lambda x: x['created'], reverse=True)

        return jsonify({
            'projects': projects,
            'total': len(projects)
        })

    except Exception as e:
        logger.error(f"Error listing projects: {e}")
        return jsonify({'error': f'Failed to list projects: {str(e)}'}), 500


# Cleanup old project files periodically (older than 24 hours)
def cleanup_old_projects():
    """Clean up projects older than 24 hours."""
    try:
        if not os.path.exists(UPLOAD_FOLDER):
            return

        cutoff_time = datetime.now() - timedelta(hours=24)
        
        for item in os.listdir(UPLOAD_FOLDER):
            project_path = os.path.join(UPLOAD_FOLDER, item)
            if os.path.isdir(project_path):
                try:
                    creation_time = datetime.fromtimestamp(os.path.getctime(project_path))
                    if creation_time < cutoff_time:
                        logger.info(f"Cleaning up old project: {item}")
                        shutil.rmtree(project_path)
                        
                        # Clean up tracking data
                        global file_tracker
                        if file_tracker is not None:
                            if item in file_tracker.project_changes:
                                del file_tracker.project_changes[item]
                            
                            keys_to_remove = [k for k in file_tracker.file_hashes.keys() if k.startswith(f"{item}:")]
                            for key in keys_to_remove:
                                del file_tracker.file_hashes[key]

                except Exception as e:
                    logger.warning(f"Error cleaning up project {item}: {e}")

    except Exception as e:
        logger.error(f"Error in cleanup_old_projects: {e}")


# Schedule cleanup to run periodically
def schedule_cleanup():
    """Schedule periodic cleanup of old projects."""
    cleanup_old_projects()
    # Schedule next cleanup in 1 hour
    timer = threading.Timer(3600.0, schedule_cleanup)
    timer.daemon = True
    timer.start()


def parse_download_line(line: str) -> Dict[str, Any]:
    """Parse download progress line from Ollama."""
    progress_info = {
        'status': 'unknown',
        'progress': 0,
        'message': line.strip()
    }

    try:
        # Try to parse JSON
        if line.strip().startswith('{'):
            data = json.loads(line.strip())
            
            if 'status' in data:
                progress_info['status'] = data['status']
                progress_info['message'] = data['status']
                
                if 'completed' in data and 'total' in data:
                    total = data['total']
                    completed = data['completed']
                    if total > 0:
                        progress_info['progress'] = (completed / total) * 100
                        progress_info['message'] = f"{data['status']}: {completed}/{total} bytes ({progress_info['progress']:.1f}%)"
                
                elif progress_info['status'] == 'success':
                    progress_info['progress'] = 100
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
                    progress_info['message'] = 'Download completed successfully'

        else:
            # Handle non-JSON lines
            lower_line = line.lower()
    # Process layer download progress
            if 'pulling' in lower_line:
                progress_info['status'] = 'pulling'
                progress_info['message'] = line.strip()
            elif 'verifying' in lower_line:
                progress_info['status'] = 'verifying'
                progress_info['progress'] = 90
                progress_info['message'] = line.strip()
            elif 'success' in lower_line or 'complete' in lower_line:
                progress_info['status'] = 'success'
                progress_info['progress'] = 100
                progress_info['message'] = 'Download completed successfully'
            elif 'error' in lower_line or 'failed' in lower_line:
                progress_info['status'] = 'error'
                progress_info['message'] = line.strip()

    except json.JSONDecodeError:
        # If JSON parsing fails, treat as plain text
        progress_info['message'] = line.strip()

    return progress_info


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
@app.route('/api/health')
def health_check():
    """Health check endpoint."""
    try:
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

        # Check Ollama connection
        ollama_status = check_ollama_connection()
        
        # Get available models
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
        available_models = get_available_models()
        
        # Get system info
        upload_dir_exists = os.path.exists(UPLOAD_FOLDER)
        upload_dir_writable = os.access(UPLOAD_FOLDER, os.W_OK) if upload_dir_exists else False
        
        # Count projects
        project_count = 0
        if upload_dir_exists:
            try:
                project_count = len([item for item in os.listdir(UPLOAD_FOLDER) 
                                   if os.path.isdir(os.path.join(UPLOAD_FOLDER, item))])
            except OSError:
                project_count = 0

        health_status = {
            'status': 'healthy' if ollama_status else 'degraded',
            'timestamp': datetime.now().isoformat(),
            'services': {
                'ollama': {

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
            'status': 'up' if ollama_status else 'down',
            'url': get_ollama_url(),
            'available_models': available_models,
            'model_count': len(available_models)
        },
        'file_system': {
            'upload_dir_exists': upload_dir_exists,
            'upload_dir_writable': upload_dir_writable,
            'project_count': project_count
        }
    },
    'configuration': {
        'upload_folder': UPLOAD_FOLDER,
        'max_content_length': MAX_CONTENT_LENGTH,
        'allowed_extensions': list(ALLOWED_EXTENSIONS),
        'auto_download_disabled': AUTO_DOWNLOAD_DISABLED
    }
}

status_code = 200 if ollama_status else 503
return jsonify(health_status), status_code
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
        return jsonify({
            'status': 'error',
            'timestamp': datetime.now().isoformat(),
            'error': str(e)
        }), 500


@app.route('/api/chat', methods=['POST'])
def chat():
    """Handle chat requests with project context."""
    try:
        if not check_ollama_connection():
            return jsonify({'error': 'Ollama service is not available'}), 503

        data = request.get_json()
        message = data.get('message', '').strip()
        project_id = data.get('project_id')
        model = data.get('model', active_model or 'llama2')

        if not message:
            return jsonify({'error': 'Message is required'}), 400

        # Prepare context
        context = ""
        if project_id:
            enhanced_context = get_enhanced_chat_context(project_id)
            
            if enhanced_context['project_analysis']:
                analysis = enhanced_context['project_analysis']
                context += f"Project Context:\n"
                context += f"- Type: {analysis['project_type']}\n"
                context += f"- Technologies: {', '.join(analysis['detected_technologies'])}\n"
                context += f"- Files: {analysis['file_count']}\n"
                context += f"- Main files: {', '.join(analysis['main_files'])}\n\n"

            if enhanced_context['recent_changes']:
                context += "Recent Changes:\n"
                for change in enhanced_context['recent_changes'][:3]:
                    context += f"- {change['operation']} {change['file_path']} ({change['timestamp']})\n"
                # Create a system prompt that's aware of file changes
                context += "\n"

        # Prepare full prompt
        full_prompt = context + message if context else message

        # Make request to Ollama
        response = requests.post(
            f"{get_ollama_url()}/api/generate",
            json={
                'model': model,
                'prompt': full_prompt,
                'stream': False
            },
            timeout=300
        )

        if response.status_code == 200:
            result = response.json()
            return jsonify({
                'response': result.get('response', ''),
                'model': model,
                'context_used': bool(context),
                'project_id': project_id
            })
        else:
            return jsonify({
                'error': f'Ollama API error: {response.status_code}'
            }), response.status_code

    except requests.exceptions.Timeout:
        return jsonify({'error': 'Request timeout - response took too long'}), 504
    except requests.exceptions.RequestException as e:
        return jsonify({'error': f'Request failed: {str(e)}'}), 503
    except Exception as e:
        logger.error(f"Chat error: {e}")
        return jsonify({'error': f'Chat failed: {str(e)}'}), 500


@app.route('/api/download', methods=['POST'])
def download_model():
    """Download a model via Ollama."""
    global download_progress, AUTO_DOWNLOAD_DISABLED

    if AUTO_DOWNLOAD_DISABLED:
        return jsonify({'error': 'Model downloads are disabled'}), 403

    try:
        if not check_ollama_connection():
            return jsonify({'error': 'Ollama service is not available'}), 503

        # Get model ID from request
        data = request.get_json()
        model_name = data.get('model', '').strip()

        if not model_name:
            return jsonify({'error': 'Model name is required'}), 400

        # Check if model already exists
        if is_model_available(model_name):
            return jsonify({
                'error': f'Model {model_name} is already available',
                'available': True
            }), 409

        # Initialize progress tracking
        download_progress[model_name] = {
            'status': 'starting',
            'progress': 0,
            'message': 'Starting download...',
            'start_time': datetime.now().isoformat()
        }

        def download_worker():
            try:
                # Make streaming request to Ollama
                response = requests.post(
                    f"{get_ollama_url()}/api/pull",
                    json={'name': model_name},
                    stream=True,
                    timeout=3600  # 1 hour timeout
                )

                if response.status_code == 200:
                    for line in response.iter_lines():
                        if line:
                            try:
                                line_str = line.decode('utf-8')
                                progress_info = parse_download_line(line_str)
                                
                        # Update time if progress changed
                                download_progress[model_name].update(progress_info)
                                download_progress[model_name]['last_update'] = datetime.now().isoformat()

                                # Check if download completed
                                if progress_info['status'] == 'success' or progress_info['progress'] >= 100:
                                    download_progress[model_name]['status'] = 'completed'
                                    download_progress[model_name]['progress'] = 100
                                    download_progress[model_name]['message'] = 'Download completed successfully'
                                    download_progress[model_name]['end_time'] = datetime.now().isoformat()
                                    
                                    # Clear the cached model list
                                    global model_status_cache
                                    model_status_cache.clear()
                                    break

                                elif progress_info['status'] == 'error':
                                    download_progress[model_name]['status'] = 'error'
                                    download_progress[model_name]['end_time'] = datetime.now().isoformat()
                                    break

                            except Exception as e:
                                logger.error(f"Error parsing download line: {e}")
                                continue

                else:
                    download_progress[model_name]['status'] = 'error'
                    download_progress[model_name]['message'] = f'HTTP {response.status_code}: {response.text}'
                    download_progress[model_name]['end_time'] = datetime.now().isoformat()

            except requests.exceptions.Timeout:
                download_progress[model_name]['status'] = 'error'
                download_progress[model_name]['message'] = 'Download timeout'
                download_progress[model_name]['end_time'] = datetime.now().isoformat()
            except Exception as e:
                download_progress[model_name]['status'] = 'error'
                download_progress[model_name]['message'] = f'Download failed: {str(e)}'
                download_progress[model_name]['end_time'] = datetime.now().isoformat()

        # Start download in background thread
        thread = threading.Thread(target=download_worker)
        thread.daemon = True
        thread.start()

        return jsonify({
            'message': f'Started downloading {model_name}',
            'model': model_name,
            'progress': download_progress[model_name]
        })

    except Exception as e:
        logger.error(f"Download initiation error: {e}")
        return jsonify({'error': f'Failed to start download: {str(e)}'}), 500


@app.route('/api/download/reset', methods=['POST'])
def reset_download_state():
    """Reset download state for a model."""
    try:
        data = request.get_json()
        model_name = data.get('model', '').strip()

        if not model_name:
            return jsonify({'error': 'Model name is required'}), 400

        global download_progress
        if model_name in download_progress:
            del download_progress[model_name]

        return jsonify({
            'message': f'Reset download state for {model_name}',
            'model': model_name
        })

    except Exception as e:
        logger.error(f"Reset download error: {e}")
        return jsonify({'error': f'Failed to reset download: {str(e)}'}), 500


@app.route('/api/debug')
def debug_status():
    """Debug endpoint for troubleshooting."""
    try:
        debug_info = {
            'timestamp': datetime.now().isoformat(),
            'ollama': {
                'host': ollama_host,
                'port': ollama_port,
                'url': get_ollama_url(),
                'connection': check_ollama_connection(),
                'available_models': get_available_models()
            },
            'app': {
                'active_model': active_model,
                'auto_download_disabled': AUTO_DOWNLOAD_DISABLED,
                'upload_folder': UPLOAD_FOLDER,
                'max_content_length': MAX_CONTENT_LENGTH
            },
            'downloads': download_progress,
            'file_system': {
                'upload_folder_exists': os.path.exists(UPLOAD_FOLDER),
                'upload_folder_writable': os.access(UPLOAD_FOLDER, os.W_OK) if os.path.exists(UPLOAD_FOLDER) else False
            }
        }

        return jsonify(debug_info)

    except Exception as e:
        logger.error(f"Debug endpoint error: {e}")
        return jsonify({
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500


@app.route('/terraform-sandbox')
def terraform_sandbox():
    """Terraform sandbox page."""
    return render_template('terraform_sandbox.html')


# Duplicate routes (these seem to be duplicates from original code)
@app.route('/api/terraform-redirect')
def status_no_download():
    """Get status without download capability."""
    try:
        if not check_ollama_connection():
            return jsonify({

                'connected': False,
                'error': 'Cannot connect to Ollama service',
                'url': get_ollama_url()
            }), 503

        available_models = get_available_models()
        
        return jsonify({
            'connected': True,
            'url': get_ollama_url(),
            'models': available_models,
            'active_model': active_model,
            'total_models': len(available_models),
            'auto_download_disabled': True
        })

    except Exception as e:
        logger.error(f"Status error: {e}")
        return jsonify({
            'connected': False,
            'error': str(e),
            'url': get_ollama_url()
        }), 500


@app.route('/api/status-with-download')
def status():
    """Get status with download capability."""
    try:
        if not check_ollama_connection():
            return jsonify({

                'connected': False,
                'error': 'Cannot connect to Ollama service',
                'url': get_ollama_url()
            }), 503

        available_models = get_available_models()
        
        return jsonify({
            'connected': True,
            'url': get_ollama_url(),
            'models': available_models,
            'active_model': active_model,
            'total_models': len(available_models),
            'auto_download_disabled': AUTO_DOWNLOAD_DISABLED
        })

    except ConnectionError as e:
        return jsonify({
            'connected': False,
            'error': f'Connection error: {str(e)}',
            'url': get_ollama_url()
        }), 503
    except Exception as e:
        logger.error(f"Status error: {e}")
        return jsonify({
            'connected': False,
            'error': str(e),
            'url': get_ollama_url()
        }), 500


# Duplicate download route
@app.route('/api/download-duplicate', methods=['POST'])
def download_model_duplicate():
    """Duplicate download endpoint."""
    global download_progress, AUTO_DOWNLOAD_DISABLED

    if AUTO_DOWNLOAD_DISABLED:
        return jsonify({'error': 'Model downloads are disabled'}), 403

    try:
        if not check_ollama_connection():
            return jsonify({'error': 'Ollama service is not available'}), 503

        # Get model ID from request
        data = request.get_json()
        model_name = data.get('model', '').strip()

        if not model_name:
            return jsonify({'error': 'Model name is required'}), 400

        # Check if model already exists
        if is_model_available(model_name):
            return jsonify({
                'error': f'Model {model_name} is already available',
                'available': True
            }), 409

        # Initialize progress tracking
        download_progress[model_name] = {
            'status': 'starting',
            'progress': 0,
            'message': 'Starting download...',
            'start_time': datetime.now().isoformat()
        }

        def download_worker():
            try:
                response = requests.post(
                    f"{get_ollama_url()}/api/pull",
                    json={'name': model_name},
                    stream=True,
                    timeout=3600
                )

                if response.status_code == 200:
                    for line in response.iter_lines():
                        if line:
                            try:
                                line_str = line.decode('utf-8')
                                progress_info = parse_download_line(line_str)
                                
                        # Update time if progress changed
                                download_progress[model_name].update(progress_info)
                                download_progress[model_name]['last_update'] = datetime.now().isoformat()

                                if progress_info['status'] == 'success' or progress_info['progress'] >= 100:
                                    download_progress[model_name]['status'] = 'completed'
                                    download_progress[model_name]['progress'] = 100
                                    download_progress[model_name]['message'] = 'Download completed successfully'
                                    download_progress[model_name]['end_time'] = datetime.now().isoformat()
                                    
                                    global model_status_cache
                                    model_status_cache.clear()
                                    break

                                elif progress_info['status'] == 'error':
                                    download_progress[model_name]['status'] = 'error'
                                    download_progress[model_name]['end_time'] = datetime.now().isoformat()
                                    break

                            except Exception as e:
                                logger.error(f"Error parsing download line: {e}")
                                continue

                else:
                    download_progress[model_name]['status'] = 'error'
                    download_progress[model_name]['message'] = f'HTTP {response.status_code}: {response.text}'
                    download_progress[model_name]['end_time'] = datetime.now().isoformat()

            except requests.exceptions.Timeout:
                download_progress[model_name]['status'] = 'error'
                download_progress[model_name]['message'] = 'Download timeout'
                download_progress[model_name]['end_time'] = datetime.now().isoformat()
            except Exception as e:
                download_progress[model_name]['status'] = 'error'
                download_progress[model_name]['message'] = f'Download failed: {str(e)}'
                download_progress[model_name]['end_time'] = datetime.now().isoformat()

        # Start download in background thread
        thread = threading.Thread(target=download_worker)
        thread.daemon = True
        thread.start()

        return jsonify({
            'message': f'Started downloading {model_name}',
            'model': model_name,
            'progress': download_progress[model_name]
        })

    except Exception as e:
        logger.error(f"Download initiation error: {e}")
        return jsonify({'error': f'Failed to start download: {str(e)}'}), 500


# Duplicate reset endpoint
@app.route('/api/download-duplicate/reset', methods=['POST'])
def reset_download_state_duplicate():
    """Duplicate reset download state endpoint."""
    try:
        data = request.get_json()
        model_name = data.get('model', '').strip()

        if not model_name:
            return jsonify({'error': 'Model name is required'}), 400

        global download_progress
        if model_name in download_progress:
            del download_progress[model_name]

        return jsonify({
            'message': f'Reset download state for {model_name}',
            'model': model_name
        })

    except Exception as e:
        logger.error(f"Reset download error: {e}")
        return jsonify({'error': f'Failed to reset download: {str(e)}'}), 500


# Duplicate debug endpoint
            'success': False,
            'error': str(e)
        })

@app.route('/api/debug-duplicate')
def debug_status_duplicate():
    """Duplicate debug endpoint."""
    try:
        debug_info = {
            'timestamp': datetime.now().isoformat(),
            'ollama': {
                'host': ollama_host,
                'port': ollama_port,
                'url': get_ollama_url(),
                'connection': check_ollama_connection(),
                'available_models': get_available_models()
            },
            'app': {
                'active_model': active_model,
                'auto_download_disabled': AUTO_DOWNLOAD_DISABLED,
                'upload_folder': UPLOAD_FOLDER,
                'max_content_length': MAX_CONTENT_LENGTH
            },
            'downloads': download_progress,
            'file_system': {
                'upload_folder_exists': os.path.exists(UPLOAD_FOLDER),
                'upload_folder_writable': os.access(UPLOAD_FOLDER, os.W_OK) if os.path.exists(UPLOAD_FOLDER) else False
            }
        }

        return jsonify(debug_info)

    except Exception as e:
        logger.error(f"Debug endpoint error: {e}")
        return jsonify({
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500


# Duplicate terraform route
@app.route('/terraform-sandbox-duplicate')
def terraform_redirect():
    """Redirect to terraform sandbox URL."""
    return redirect(TERRAFORM_SANDBOX_URL, code=302)


# Rest of your routes and code...
    return render_template('terraform_sandbox.html')

# Error handlers
@app.errorhandler(404)
def page_not_found(e):
    return render_template('error.html', 
                          error_code=404, 
                          error_title="Not Found", 
                          error_message="The requested URL was not found on the server. If you entered the URL manually please check your spelling and try again."), 404

# Add route for Terraform sandbox
@app.route('/terraform/sandbox')
def terraform_sandbox():
    return render_template('terraform_sandbox.html')


# Run the application
if __name__ == '__main__':
    # Initialize Flask app
    app = Flask(__name__)
    app.config['SECRET_KEY'] = secret_key or 'your-secret-key-here'
    app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
    app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH

    # Create upload directory
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)

    # Initialize file tracker
    file_tracker = FileChangeTracker()

    # Start periodic cleanup
    schedule_cleanup()

    # Set configuration from environment
    TERRAFORM_SANDBOX_URL = os.getenv('TERRAFORM_SANDBOX_URL', 'http://localhost:3000')
    host = os.getenv('FLASK_HOST', '0.0.0.0')
    port = int(os.getenv('FLASK_PORT', 5000))
    debug = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'

    # Run the application
    app.run(host=host, port=port, debug=debug)