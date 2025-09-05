```bash
#!/bin/bash

# RHEL 9.x Terraform LLM Assistant - Complete One-Script Deployment
# Creates Docker container with Ollama, CodeLlama models, and web interface

set -euo pipefail

# Configuration
PROJECT_NAME="terraform-llm-assistant"
INSTALL_DIR="/opt/terraform-llm"
MODEL_SIZE="${MODEL_SIZE:-13b}"
WEB_PORT="${WEB_PORT:-5000}"
OLLAMA_PORT="${OLLAMA_PORT:-11434}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

log() {
    echo -e "${BLUE}[$(date +'%H:%M:%S')]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[$(date +'%H:%M:%S')] ✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}[$(date +'%H:%M:%S')] ⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}[$(date +'%H:%M:%S')] ❌ $1${NC}"
}

check_rhel_version() {
    if [[ ! -f /etc/redhat-release ]]; then
        log_error "This script is designed for RHEL systems only"
        exit 1
    fi
    
    local rhel_version=$(grep -oE 'release [0-9]+' /etc/redhat-release | awk '{print $2}')
    if [[ ${rhel_version} -ne 9 ]]; then
        log_error "This script requires RHEL 9.x (detected: RHEL ${rhel_version})"
        exit 1
    fi
    
    log_success "RHEL 9.x detected"
}

check_root() {
    if [[ $EUID -ne 0 ]]; then
        log_error "This script must be run as root"
        echo "Run with: sudo $0"
        exit 1
    fi
}

# confirm() - centralize prompt/yes/no logic
confirm() {
  local prompt="$1"
  local default="${2:-N}"
  local yn re

  case "$default" in
    [yY]*) yn="y/N"; re="^[Yy]";;
    *)     yn="Y/n"; re="^[Yy]";;
  esac

  while true; do
    read -r -p "$prompt ($yn): " response
    if [[ -z "$response" ]]; then
      response="$default"
    fi
    if [[ "$response" =~ $re ]]; then
      return 0
    fi
    if [[ "$response" =~ ^[Nn] ]]; then
      return 1
    fi
    echo "Please answer yes or no."
  done
}

# ... existing header and color/log helpers ...

# Parse arguments (additions)
DATA_DIR="${LLM_DATA_DIR:-}"
FORCE_YES="${FORCE_YES:-0}"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --data-dir)
      DATA_DIR="$2"; shift 2 ;;
    --force-yes)
      FORCE_YES=1; shift ;;
    *)
      shift ;;
  esac
done

# confirm() function from previous change assumed to be present

free_space_gb() {
  # Returns integer GiB free on the filesystem backing the given path
  local path="${1:-/}"
  # df works on existing paths; if the path doesn't exist yet, check its parent
  if [[ ! -e "$path" ]]; then
    path="$(dirname "$path")"
  fi
  df -Pk "$path" 2>/dev/null | awk 'NR==2 {print int($4/1024/1024)}'
}

ensure_dir_writable() {
  local dir="$1"
  mkdir -p "$dir" 2>/dev/null || return 1
  [[ -w "$dir" ]] || return 1
}

prompt_data_dir() {
  local required_space_gb="$1"
  local choice path fs gb
  local -a candidates=(
    "/data/llm"
    "/mnt/llm"
    "/opt/llm"
    "/var/lib/llm"
    "$HOME/llm-data"
    "$PWD/llm-data"
  )

  echo
  echo "Select a storage directory for models and artifacts (need at least ${required_space_gb}GB free):"
  local i=1
  for path in "${candidates[@]}"; do
    gb="$(free_space_gb "$(dirname "$path")")"
    printf "  %d) %-30s  (free: %sGB)\n" "$i" "$path" "${gb:-0}"
    ((i++))
  done
  echo "  0) Enter a custom path"

  while true; do
    read -r -p "Choice [0-$((i-1))]: " choice
    if [[ "$choice" =~ ^[0-9]+$ ]]; then
      if [[ "$choice" -eq 0 ]]; then
        read -r -p "Enter full path: " path
      elif (( choice >= 1 && choice < i )); then
        path="${candidates[$((choice-1))]}"
      else
        echo "Invalid choice."
        continue
      fi
    else
      echo "Please enter a number."
      continue
    fi

    [[ -z "$path" ]] && { echo "Path cannot be empty."; continue; }

    # Ensure parent exists; try to create target and check write access
    if ! ensure_dir_writable "$path"; then
      echo "Cannot write to $path. Try another location or adjust permissions."
      continue
    fi

    gb="$(free_space_gb "$path")"
    gb="${gb:-0}"
    if (( gb < required_space_gb )); then
      echo "Only ${gb}GB free at $path, need ${required_space_gb}GB. Choose another location."
      continue
    fi

    DATA_DIR="$path"
    export LLM_DATA_DIR="$DATA_DIR"
    export TF_VAR_data_dir="$DATA_DIR"
    log_success "Using data directory: $DATA_DIR (${gb}GB free)"
    return 0
  done
}

check_system_requirements() {
  log "Checking system requirements..."

  # Memory check
  local total_memory_gb
  total_memory_gb=$(free -g | awk 'NR==2{print $2}')
  local required_memory=8

  if [[ $MODEL_SIZE == "34b" ]]; then
      required_memory=32
  elif [[ $MODEL_SIZE == "13b" ]]; then
      required_memory=16
  fi

  if [[ $total_memory_gb -lt $required_memory ]]; then
      log_warning "System has ${total_memory_gb}GB RAM, ${required_memory}GB recommended for ${MODEL_SIZE} model"
      if ! confirm "Continue anyway?" "N"; then
          exit 1
      fi
  else
      log_success "Memory: ${total_memory_gb}GB (sufficient for ${MODEL_SIZE} model)"
  fi

  # Disk space requirement based on model size
  local required_space=25
  if [[ $MODEL_SIZE == "34b" ]]; then
      required_space=50
  fi

  # If a data dir is pre-specified, validate it; otherwise, fall back to root and offer selection if insufficient
  if [[ -n "$DATA_DIR" ]]; then
    if ! ensure_dir_writable "$DATA_DIR"; then
      log_error "Data directory not writable: $DATA_DIR"
      exit 1
    fi
    local free_gb
    free_gb="$(free_space_gb "$DATA_DIR")"
    free_gb="${free_gb:-0}"
    if (( free_gb < required_space )); then
      if [[ "$FORCE_YES" == "1" ]]; then
        log_warning "Only ${free_gb}GB free in $DATA_DIR; required ${required_space}GB. Continuing due to FORCE_YES"
      else
        log_error "Insufficient disk space in $DATA_DIR. Need ${required_space}GB, have ${free_gb}GB"
        exit 1
      fi
    fi
    log_success "Disk space in $DATA_DIR: ${free_gb}GB free (need ${required_space}GB)"
  else
    # No pre-specified data dir
    local root_free_gb
    root_free_gb="$(free_space_gb)"
    if (( root_free_gb < required_space )); then
      # Not enough on root; offer selection
      prompt_data_dir "$required_space" || exit 1
    else
      # Enough on root, default to it
      DATA_DIR="/var/lib/terraform-llm"  # Reasonable default?
      export LLM_DATA_DIR="$DATA_DIR"
      export TF_VAR_data_dir="$DATA_DIR"
      log_success "Using default data directory: $DATA_DIR (${root_free_gb}GB free)"
    fi
  fi
}

install_docker() {
    log "Installing Docker..."
    
    # Remove any old Docker packages
    dnf remove -y docker docker-client docker-client-latest docker-common docker-latest \
        docker-latest-logrotate docker-logrotate docker-engine podman runc 2>/dev/null || true
    
    # Install required packages
    dnf install -y dnf-plugins-core
    
    # Add Docker repository
    dnf config-manager --add-repo https://download.docker.com/linux/rhel/docker-ce.repo
    
    # Install Docker
    dnf install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    
    # Start and enable Docker
    systemctl start docker
    systemctl enable docker
    
    # Add current user to docker group (if not root)
    if [[ -n "${SUDO_USER:-}" ]]; then
        usermod -aG docker "${SUDO_USER}"
        log_success "Added ${SUDO_USER} to docker group"
        log_warning "Log out and back in for group changes to take effect"
    fi
    
    # Test Docker
    if docker run --rm hello-world >/dev/null 2>&1; then
        log_success "Docker installed and working"
    else
        log_error "Docker installation failed"
        exit 1
    fi
}

check_docker() {
    if command -v docker >/dev/null 2>&1 && systemctl is-active --quiet docker; then
        log_success "Docker is installed and running"
        return 0
    elif command -v docker >/dev/null 2>&1; then
        log "Starting Docker service..."
        systemctl start docker
        systemctl enable docker
        log_success "Docker service started"
        return 0
    else
        log "Docker not found, installing..."
        install_docker
        return 0
    fi
}

create_project_structure() {
    log "Creating project structure at ${INSTALL_DIR}..."
    
    # Remove existing installation if present
    if [[ -d "${INSTALL_DIR}" ]]; then
        log_warning "Removing existing installation..."
        rm -rf "${INSTALL_DIR}"
    fi
    
    mkdir -p "${INSTALL_DIR}/app"
    cd "${INSTALL_DIR}"
    
    log_success "Project directory created"
}

create_dockerfile() {
    log "Creating Dockerfile..."
    
    cat > Dockerfile << 'DOCKERFILEEOF'
# RHEL 9 Terraform LLM Assistant - Complete Container
FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive
ENV OLLAMA_HOST=0.0.0.0
ENV OLLAMA_ORIGINS=*
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    git \
    build-essential \
    procps \
    wget \
    gnupg \
    software-properties-common \
    && rm -rf /var/lib/apt/lists/*

# Install Ollama
RUN curl -fsSL https://ollama.ai/install.sh | sh

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir \
    chromadb>=0.4.15 \
    sentence-transformers>=2.2.2 \
    requests>=2.31.0 \
    numpy>=1.24.3 \
    torch>=2.0.0 \
    transformers>=4.30.0 \
    huggingface-hub>=0.16.4 \
    tokenizers>=0.13.3 \
    tqdm>=4.65.0 \
    pyyaml>=6.0 \
    click>=8.1.0 \
    colorama>=0.4.6 \
    flask>=3.0.0 \
    werkzeug>=3.0.0 \
    gunicorn>=21.2.0

# Copy application files
COPY app/ ./

RUN chmod +x /app/entrypoint.sh

# Create CLI wrapper
RUN echo '#!/bin/bash\ncd /app\npython3 terraform_llm_assistant.py "$@"' > /usr/local/bin/terraform-llm && \
    chmod +x /usr/local/bin/terraform-llm

# Create non-root user
RUN useradd -m -u 1000 terraform-user && \
    chown -R terraform-user:terraform-user /app

EXPOSE 5000 11434
VOLUME ["/root/.ollama", "/app/data"]

HEALTHCHECK --interval=30s --timeout=30s --start-period=300s --retries=3 \
    CMD curl -f http://localhost:5000/health && curl -f http://localhost:11434/api/tags || exit 1

ENTRYPOINT ["/app/entrypoint.sh"]
DOCKERFILEEOF

    log_success "Dockerfile created"
}

create_docker_compose() {
    log "Creating docker-compose.yml..."
    
    # Set memory limits based on model size
    local memory_limit
    local memory_reservation
    
    case $MODEL_SIZE in
        "7b")
            memory_limit="12G"
            memory_reservation="8G"
            ;;
        "34b")
            memory_limit="48G"
            memory_reservation="24G"
            ;;
        *)
            memory_limit="20G"
            memory_reservation="12G"
            ;;
    esac
    
    cat > docker-compose.yml << COMPOSEEOF
version: '3.8'

services:
  terraform-llm:
    build: .
    container_name: ${PROJECT_NAME}
    ports:
      - "${WEB_PORT}:5000"
      - "${OLLAMA_PORT}:11434"
    volumes:
      - ollama_models:/root/.ollama
      - app_data:/app/data
      - type: tmpfs
        target: /tmp
        tmpfs:
          size: 2G
    environment:
      - OLLAMA_HOST=0.0.0.0
      - OLLAMA_ORIGINS=*
      - PYTHONUNBUFFERED=1
      - MODEL_NAME=codellama:${MODEL_SIZE}-instruct
      - INSTALL_DATE=$(date)
    restart: unless-stopped
    deploy:
      resources:
        limits:
          memory: ${memory_limit}
          cpus: '4.0'
        reservations:
          memory: ${memory_reservation}
          cpus: '2.0'
    healthcheck:
      test: ["CMD-SHELL", "curl -f http://localhost:5000/health && curl -f http://localhost:11434/api/tags || exit 1"]
      interval: 30s
      timeout: 30s
      retries: 5
      start_period: 900s
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"

volumes:
  ollama_models:
  app_data:
COMPOSEEOF

    log_success "Docker Compose configuration created"
}

create_llm_assistant() {
    log "Creating LLM assistant application..."
    
    cat > app/terraform_llm_assistant.py << 'PYTHONEOF'
#!/usr/bin/env python3
"""
Terraform/AWS LLM Assistant for RHEL 9.x
Complete Infrastructure as Code assistant with RAG capabilities
"""

import os
import json
import sys
import requests
import time
from pathlib import Path
from typing import List, Dict, Optional
import click
from colorama import init, Fore, Style

# Import with error handling
try:
    import chromadb
    from sentence_transformers import SentenceTransformer
    DEPS_OK = True
except ImportError as e:
    print(f"Warning: {e}")
    DEPS_OK = False

init(autoreset=True)

class TerraformLLMAssistant:
    def __init__(self, model_name=None):
        self.ollama_url = "http://localhost:11434"
        self.model = model_name or os.environ.get('MODEL_NAME', 'codellama:13b-instruct')
        self.embedding_model = None
        self.chroma_client = None
        self.collection = None
        
        # RHEL 9 optimized knowledge base
        self.knowledge_base = {
            "s3_rhel": """
# S3 Bucket for RHEL 9 System Backups
resource "aws_s3_bucket" "rhel_backups" {
  bucket = "${var.environment}-rhel9-backups"
  tags = merge(var.common_tags, {
    Purpose = "RHEL9_System_Backups"
    OS      = "RHEL9"
  })
}

resource "aws_s3_bucket_versioning" "rhel_backups" {
  bucket = aws_s3_bucket.rhel_backups.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "rhel_backups" {
  bucket = aws_s3_bucket.rhel_backups.id
  
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = aws_kms_key.rhel_backups.arn
    }
    bucket_key_enabled = true
  }
}

resource "aws_kms_key" "rhel_backups" {
  description = "KMS key for RHEL 9 backup encryption"
  
  tags = merge(var.common_tags, {
    Name    = "${var.environment}-rhel9-backup-key"
    Purpose = "RHEL9_Backup_Encryption"
  })
}
""",
            "rhel_instance": """
# RHEL 9 Instance with Security Hardening
data "aws_ami" "rhel9" {
  most_recent = true
  owners      = ["309956199498"] # Red Hat
  
  filter {
    name   = "name"
    values = ["RHEL-9.*-x86_64-*"]
  }
  
  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

resource "aws_security_group" "rhel9_web" {
  name_prefix = "${var.project_name}-rhel9-"
  vpc_id      = var.vpc_id
  description = "Security group for RHEL 9 web servers"
  
  # HTTPS only
  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "HTTPS traffic"
  }
  
  # SSH from management networks
  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = var.mgmt_cidrs
    description = "SSH from management networks"
  }
  
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
  
  tags = merge(var.common_tags, {
    OS = "RHEL9"
  })
}

resource "aws_instance" "rhel9_web" {
  count = var.instance_count
  
  ami                    = data.aws_ami.rhel9.id
  instance_type          = var.instance_type
  key_name              = var.key_pair_name
  vpc_security_group_ids = [aws_security_group.rhel9_web.id]
  subnet_id             = var.subnet_ids[count.index % length(var.subnet_ids)]
  
  # Instance metadata service v2 only
  metadata_options {
    http_endpoint = "enabled"
    http_tokens   = "required"
    http_put_response_hop_limit = 1
  }
  
  # EBS optimization
  ebs_optimized = true
  monitoring    = true
  
  root_block_device {
    volume_type = "gp3"
    volume_size = var.root_volume_size
    iops        = 3000
    throughput  = 125
    encrypted   = true
    kms_key_id  = var.kms_key_id
  }
  
  user_data = base64encode(templatefile("${path.module}/rhel9_user_data.sh", {
    hostname = "${var.project_name}-rhel9-${count.index + 1}"
  }))
  
  tags = merge(var.common_tags, {
    Name = "${var.project_name}-rhel9-${count.index + 1}"
    OS   = "RHEL9"
  })
}
"""
        }
    
    def setup_models(self):
        """Initialize embedding model and ChromaDB"""
        if not DEPS_OK:
            print("Warning: Dependencies not available, RAG features disabled")
            return False
            
        try:
            print(f"{Fore.YELLOW}📄 Loading embedding model...")
            self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
            self.chroma_client = chromadb.Client()
            
            try:
                self.collection = self.chroma_client.get_collection("terraform_docs")
                print(f"{Fore.GREEN}✅ Using existing knowledge base")
            except:
                self.collection = self.chroma_client.create_collection("terraform_docs")
                self.populate_knowledge_base()
                print(f"{Fore.GREEN}✅ Created new knowledge base")
                
        except Exception as e:
            print(f"{Fore.RED}❌ Error setting up models: {e}")
            return False
        return True
    
    def populate_knowledge_base(self):
        """Populate ChromaDB with Terraform/AWS examples"""
        print(f"{Fore.YELLOW}📚 Populating knowledge base...")
        
        for doc_id, content in self.knowledge_base.items():
            try:
                embedding = self.embedding_model.encode([content])
                self.collection.add(
                    embeddings=embedding.tolist(),
                    documents=[content],
                    ids=[doc_id]
                )
            except Exception as e:
                print(f"{Fore.RED}❌ Error adding {doc_id}: {e}")
    
    def check_ollama_status(self):
        """Check if Ollama is running and model is available"""
        try:
            response = requests.get(f"{self.ollama_url}/api/tags", timeout=5)
            if response.status_code == 200:
                models = response.json().get("models", [])
                model_names = [m["name"] for m in models]
                return self.model in model_names
            return False
        except:
            return False
    
    def search_knowledge_base(self, query: str, n_results: int = 2) -> List[str]:
        """Search for relevant examples"""
        if not self.embedding_model or not self.collection:
            return []
        
        try:
            query_embedding = self.embedding_model.encode([query])
            results = self.collection.query(
                query_embeddings=query_embedding.tolist(),
                n_results=n_results
            )
            return results["documents"][0] if results["documents"] else []
        except Exception as e:
            return []
    
    def generate_response(self, prompt: str, context: List[str] = None) -> str:
        """Generate response using Ollama"""
        enhanced_prompt = f"""You are an expert Terraform and AWS infrastructure engineer specializing in RHEL 9 environments. 
Provide accurate, secure, and well-documented Infrastructure as Code following enterprise best practices.

{'Context Examples:' + chr(10) + chr(10).join(context) + chr(10) if context else ''}

User Request: {prompt}

Provide complete, working Terraform code with explanations optimized for RHEL 9.

Response:"""
        
        payload = {
            "model": self.model,
            "prompt": enhanced_prompt,
            "stream": False,
            "options": {
                "temperature": 0.1,
                "top_p": 0.9,
                "num_predict": 3000
            }
        }
        
        try:
            response = requests.post(f"{self.ollama_url}/api/generate", json=payload, timeout=120)
            if response.status_code == 200:
                return response.json()["response"]
            else:
                return f"❌ API Error: {response.status_code}"
            else:
                return f"❌ API Error: {response.status_code}"
        except requests.exceptions.Timeout:
            return "❌ Request timeout. Try a simpler question."
        except Exception as e:
            return f"❌ Error: {e}"

@click.command()
@click.option('--model', help='Ollama model to use')
@click.option('--setup-only', is_flag=True, help='Only setup, don\\'t start chat')
def main(model, setup_only):
    """Terraform/AWS LLM Assistant for RHEL 9"""
    
    assistant = TerraformLLMAssistant(model)
    
    if not assistant.check_ollama_status():
        print(f"{Fore.RED}❌ Ollama not running or model not installed")
        return 1
    
    print(f"{Fore.GREEN}✅ Ollama and model ready")
    
    if not assistant.setup_models():
        print(f"{Fore.YELLOW}⚠️  Model setup issues, continuing...")
    
    if setup_only:
        print(f"{Fore.GREEN}✅ Setup complete!")
        return 0
    
    # Interactive chat for CLI
    print(f"{Fore.GREEN}🚀 Terraform LLM Ready for RHEL 9! Type 'quit' to exit")
    while True:
        try:
            question = input(f"{Fore.GREEN}You: {Style.RESET_ALL}").strip()
            if question.lower() in ['quit', 'exit', 'q']:
                break
            if question:
                docs = assistant.search_knowledge_base(question)
                response = assistant.generate_response(question, docs)
                print(f"\n{Fore.CYAN}Assistant:\n{response}\n{Style.RESET_ALL}")
        except KeyboardInterrupt:
            break
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
PYTHONEOF

    log_success "LLM assistant application created"
}

create_flask_web_app() {
    log "Creating Flask web interface..."
    
    cat > app/flask_web_app.py << 'FLASKEOF'
#!/usr/bin/env python3
"""Flask Web Interface for RHEL 9 Terraform LLM Assistant"""

import os
import json
import time
from datetime import datetime
import uuid
from flask import Flask, request, jsonify, session
from terraform_llm_assistant import TerraformLLMAssistant

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', str(uuid.uuid4()))

# Initialize LLM assistant
llm_assistant = TerraformLLMAssistant()

@app.route('/')
def index():
    return '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Terraform LLM - RHEL 9</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: system-ui;
            background: linear-gradient(135deg, #ee5a24 0%, #c44569 100%);
            min-height: 100vh; display: flex; justify-content: center; align-items: center; padding: 20px;
        }
        .container {
            background: white; border-radius: 20px; box-shadow: 0 20px 40px rgba(0,0,0,0.1);
            width: 100%; max-width: 1200px; height: 85vh; display: flex; flex-direction: column;
        }
        .header {
            background: linear-gradient(90deg, #ee5a24, #c44569); color: white; padding: 20px 30px;
            border-radius: 20px 20px 0 0; display: flex; justify-content: space-between; align-items: center;
        }
        .header h1 { font-size: 24px; margin-bottom: 5px; }
        .header p { opacity: 0.9; font-size: 14px; }
        .rhel-badge {
            background: rgba(255,255,255,0.2); padding: 8px 15px; border-radius: 20px;
            font-size: 12px; font-weight: bold;
        }
        .status { padding: 15px 30px; background: #d4edda; color: #155724; font-size: 14px; }
        .examples { padding: 15px 30px; background: #f8f9fa; border-bottom: 1px solid #e9ecef; }
        .example-buttons { display: flex; flex-wrap: wrap; gap: 8px; }
        .example-btn {
            padding: 6px 12px; background: white; border: 1px solid #ccc; border-radius: 15px;
            cursor: pointer; font-size: 13px; transition: all 0.3s;
        }
        .example-btn:hover { background: #ee5a24; color: white; }
        .chat-container { flex: 1; display: flex; flex-direction: column; }
        .messages { flex: 1; overflow-y: auto; padding: 20px 30px; background: #fafafa; }
        .message { margin-bottom: 20px; }
        .message.user { text-align: right; }
        .message.assistant { text-align: left; }
        .message-bubble {
            display: inline-block; max-width: 80%; padding: 15px 20px; border-radius: 20px;
            white-space: pre-wrap; word-wrap: break-word;
        }
        .user .message-bubble { background: #ee5a24; color: white; }
        .assistant .message-bubble { background: white; color: #333; border: 1px solid #e9ecef; }
        .input-container { padding: 20px 30px; background: white; display: flex; gap: 10px; }
        .input-box {
            flex: 1; padding: 15px 20px; border: 2px solid #e9ecef; border-radius: 25px;
            font-size: 16px; outline: none;
        }
        .input-box:focus { border-color: #ee5a24; }
        .send-btn { padding: 15px 25px; border: none; border-radius: 25px; background: #ee5a24; color: white; cursor: pointer; }
        .code-block { background: #f8f8f8; border: 1px solid #e1e8ed; border-radius: 8px; padding: 15px; margin: 10px 0; font-family: monospace; overflow-x: auto; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div>