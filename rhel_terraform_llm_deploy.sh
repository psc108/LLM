#!/bin/bash
# Install Docker Compose (handles different methods)
install_docker_compose() {
    log "Installing Docker Compose..."

    # Check if Docker Compose is already installed via plugin
    if docker compose version &>/dev/null; then
        log_success "Docker Compose plugin already installed"
        return 0
    fi

    # Check if standalone docker-compose is already installed
    if command -v docker-compose &>/dev/null; then
        log_success "Standalone docker-compose already installed"
        return 0
    fi

    # Try to install Docker Compose plugin first (recommended method)
    log "Trying to install Docker Compose plugin..."
    if dnf install -y docker-compose-plugin &>/dev/null; then
        if docker compose version &>/dev/null; then
            log_success "Docker Compose plugin installed successfully"
            return 0
        else
            log_warning "Docker Compose plugin installed but not working properly"
        fi
    else
        log_warning "Failed to install Docker Compose plugin"
    fi

    # If plugin installation failed, try standalone docker-compose
    log "Trying to install standalone docker-compose..."

    # First try with dnf
    if dnf install -y docker-compose &>/dev/null; then
        if command -v docker-compose &>/dev/null; then
            log_success "Standalone docker-compose installed successfully with dnf"
            return 0
        fi
    fi

    # If dnf failed, install docker-compose using pip (Python package manager)
    log "Installing pip for Python 3..."
    dnf install -y python3-pip &>/dev/null

    log "Installing docker-compose using pip..."
    pip3 install docker-compose &>/dev/null

    if command -v docker-compose &>/dev/null; then
        log_success "Standalone docker-compose installed successfully with pip"
        return 0
    fi

    # Last resort: Download the docker-compose binary directly
    log "Downloading docker-compose binary directly..."
    COMPOSE_VERSION="2.24.5"
    curl -L "https://github.com/docker/compose/releases/download/v${COMPOSE_VERSION}/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose

    if command -v docker-compose &>/dev/null; then
        log_success "Docker Compose binary installed successfully"
        return 0
    fi

    log_warning "All Docker Compose installation methods failed"
    log "The system will use direct docker commands instead of docker-compose"
    return 1
}
# RHEL 9.x Terraform LLM Assistant - Complete One-Script Deployment
# Creates Docker container with Ollama, CodeLlama models, and web interface

set -euo pipefail

# Configuration
PROJECT_NAME="terraform-llm-assistant"
INSTALL_DIR="/opt/terraform-llm"
PROJECT_DIR="${INSTALL_DIR}" # For compatibility with functions that use PROJECT_DIR
MODEL_SIZE="${MODEL_SIZE:-13b}"
WEB_PORT="${WEB_PORT:-5000}"
OLLAMA_PORT="${OLLAMA_PORT:-11434}"
DATA_DIR="${DATA_DIR:-}"

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

# Get free disk space in GB for a given path
get_free_space() {
    local path="$1"
    # If the path doesn't exist, check its parent
    if [[ ! -e "$path" ]]; then
        path=$(dirname "$path")
    fi
    df -BG "$path" 2>/dev/null | awk 'NR==2 {gsub("G","",$4); print $4}'
}

# Check if a directory is writable, creating it if needed
ensure_dir_writable() {
    local dir="$1"
    mkdir -p "$dir" 2>/dev/null || return 1
    [[ -w "$dir" ]] || return 1
    return 0
}

# Simple yes/no confirmation prompt
confirm() {
    local prompt="$1"
    local default="${2:-N}"
    local yn

    if [[ "$default" =~ ^[Yy] ]]; then
        yn="Y/n"
    else
        yn="y/N"
    fi

    read -p "$prompt ($yn): " response
    if [[ -z "$response" ]]; then
        response="$default"
    fi

    if [[ "$response" =~ ^[Yy] ]]; then
        return 0
    else
        return 1
    fi
}

# Interactive storage location selection
select_storage_location() {
    local required_space="$1"
    log "Scanning for storage locations with at least ${required_space}GB free space..."

    # Create array of potential locations
    local locations=(
        "/data/${PROJECT_NAME}"
        "/mnt/${PROJECT_NAME}"
        "/opt/${PROJECT_NAME}"
        "/var/lib/${PROJECT_NAME}"
        "${HOME}/${PROJECT_NAME}"
    )

    echo ""
    echo "Available storage locations:"
    echo "---------------------------"

    local i=1
    local valid_options=()
    local valid_paths=()
    local valid_spaces=()

    # Root filesystem as a reference
    local root_free=$(get_free_space "/")
    printf "  %d) %-30s (free: %sGB)\n" "$i" "/opt/${PROJECT_NAME}" "$root_free"
    valid_options+=($i)
    valid_paths+=("/opt/${PROJECT_NAME}")
    valid_spaces+=("$root_free")
    i=$((i+1))

    # Check other mount points
    local mounts=$(findmnt -lo target -t ext4,ext3,ext2,xfs,btrfs,nfs | grep -v -E '^/boot|^/dev|^/proc|^/sys')
    for mount in $mounts; do
        # Skip root as we already have it
        [[ "$mount" == "/" ]] && continue

        local path="${mount}/${PROJECT_NAME}"
        local free=$(get_free_space "$mount")

        printf "  %d) %-30s (free: %sGB)\n" "$i" "$path" "$free"
        valid_options+=($i)
        valid_paths+=("$path")
        valid_spaces+=("$free")
        i=$((i+1))
    done

    # Add custom option
    printf "  %d) Enter a custom location\n" "$i"
    valid_options+=($i)
    valid_paths+=("custom")

    # Prompt for selection
    local selection valid_choice=0
    while [[ $valid_choice -eq 0 ]]; do
        read -p "Select storage location [1-$i]: " selection

        # Validate numeric input
        if [[ ! "$selection" =~ ^[0-9]+$ ]]; then
            echo "Please enter a number."
            continue
        fi

        # Check if selection is in valid options
        if [[ " ${valid_options[*]} " =~ " $selection " ]]; then
            valid_choice=1

            # Handle custom path input
            if [[ "${valid_paths[$selection-1]}" == "custom" ]]; then
                read -p "Enter full path for installation: " custom_path
                if [[ -z "$custom_path" ]]; then
                    echo "Path cannot be empty."
                    valid_choice=0
                    continue
                fi

                # Validate custom path
                if ! ensure_dir_writable "$custom_path"; then
                    echo "Cannot create or write to $custom_path. Check permissions."
                    valid_choice=0
                    continue
                fi

                # Check space
                local free=$(get_free_space "$custom_path")
                if [[ "$free" -lt "$required_space" ]]; then
                    echo "Warning: Only ${free}GB free, ${required_space}GB recommended."
                    if ! confirm "Continue anyway?" "N"; then
                        valid_choice=0
                        continue
                    fi
                fi

                DATA_DIR="$custom_path"
            else
                # Use predefined path, check space
                local selected_path="${valid_paths[$selection-1]}"
                local free="${valid_spaces[$selection-1]}"

                if [[ "$free" -lt "$required_space" ]]; then
                    echo "Warning: Only ${free}GB free, ${required_space}GB recommended."
                    if ! confirm "Continue anyway?" "N"; then
                        valid_choice=0
                        continue
                    fi
                fi

                # Ensure it's writable
                if ! ensure_dir_writable "$selected_path"; then
                    echo "Cannot create or write to $selected_path. Check permissions."
                    valid_choice=0
                    continue
                fi

                DATA_DIR="$selected_path"
            fi
        else
            echo "Invalid selection. Please choose a number between 1 and $i."
        fi
    done

    # Update install directory
    INSTALL_DIR="$DATA_DIR"
    log_success "Using storage location: $INSTALL_DIR"
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

check_system_requirements() {
    log "Checking system requirements..."
    
    # Memory check
    local total_memory_gb=$(free -g | awk 'NR==2{print $2}')
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

    # If DATA_DIR is already set (via command line), validate it
    if [[ -n "$DATA_DIR" ]]; then
        if ! ensure_dir_writable "$DATA_DIR"; then
            log_error "Specified data directory not writable: $DATA_DIR"
            exit 1
        fi

        local free_space_gb=$(get_free_space "$DATA_DIR")
        if [[ "$free_space_gb" -lt "$required_space" ]]; then
            log_warning "Only ${free_space_gb}GB free in $DATA_DIR (need ${required_space}GB)"
            if ! confirm "Continue anyway?" "N"; then
                exit 1
            fi
        else
            log_success "Storage at $DATA_DIR: ${free_space_gb}GB free (need ${required_space}GB)"
        fi

        # Update install directory to match data dir
        INSTALL_DIR="$DATA_DIR"
        return 0
    fi

    # Check root space first as a reference
    local root_free_gb=$(get_free_space "/")

    if [[ "$root_free_gb" -lt "$required_space" ]]; then
        log_warning "Insufficient disk space on /. Need ${required_space}GB, have ${root_free_gb}GB so we need to select an alternative location."
        select_storage_location "$required_space"
    else
        log "Root filesystem has ${root_free_gb}GB free (need ${required_space}GB)"
        if confirm "Would you like to select a different storage location?" "N"; then
            select_storage_location "$required_space"
        else
            # Default path is fine, make sure it's writable
            if ! ensure_dir_writable "$INSTALL_DIR"; then
                log_warning "Default path $INSTALL_DIR is not writable."
                select_storage_location "$required_space"
            else
                log_success "Using default location: $INSTALL_DIR"
                DATA_DIR="$INSTALL_DIR"
            fi
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
    log "Installing Docker CE and related packages..."
    dnf install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin

    # Start and enable Docker
    log "Starting Docker service..."
    systemctl start docker
    sudo systemctl enable --now docker
    unset DOCKER_HOST
    sudo docker info
    sudo ./deploy.sh

    # Add current user to docker group (if not root)
    if [[ -n "${SUDO_USER:-}" ]]; then
        usermod -aG docker "${SUDO_USER}"
        log_success "Added ${SUDO_USER} to docker group"
        log_warning "Log out and back in for group changes to take effect"
    fi

    # Test Docker
    log "Testing Docker installation..."
    if docker run --rm hello-world >/dev/null 2>&1; then
        log_success "Docker installed and working"
    else
        log_error "Docker installation failed"
        exit 1
    fi

    # Install Docker Compose separately to handle potential issues
    install_docker_compose
}

# Detect and set up Docker Compose command with detailed diagnostics
setup_docker_compose() {
    log "Setting up Docker Compose..."

    # Try to install if not present
    if ! command -v docker-compose &>/dev/null && ! docker compose version &>/dev/null; then
        log "Docker Compose not found, attempting installation..."
        install_docker_compose
    fi

    # Detect which Docker Compose variant is available
    if command -v docker-compose &>/dev/null; then
        DOCKER_COMPOSE="docker-compose"
        DOCKER_COMPOSE_VERSION=$(docker-compose --version | head -n 1 || echo "unknown")
        log_success "Using standalone docker-compose: ${DOCKER_COMPOSE_VERSION}"

        # Verify it actually works
        if ! docker-compose --version &>/dev/null; then
            log_warning "docker-compose command exists but may not be working properly"
        fi
    elif docker compose version &>/dev/null; then
        DOCKER_COMPOSE="docker compose"
        DOCKER_COMPOSE_VERSION=$(docker compose version | head -n 1 || echo "unknown")
        log_success "Using Docker Compose plugin: ${DOCKER_COMPOSE_VERSION}"
    else
        DOCKER_COMPOSE=""
        log_warning "Docker Compose not available - will use direct docker commands"
    fi

    # If running non-interactively, make sure we have a valid compose command for scripts
    if [ -z "$DOCKER_COMPOSE" ] && [[ -t 0 ]]; then
        log "Attempting one more Docker Compose installation..."
        if install_docker_compose; then
            setup_docker_compose  # Re-run setup after installation
        fi
    fi

    # Create wrapper function for use in scripts
    docker_compose() {
        if [ -n "$DOCKER_COMPOSE" ]; then
            $DOCKER_COMPOSE "$@"
            return $?
        else
            log_error "Docker Compose not available"
            return 1
        fi
    }

    # Export for use in scripts
    export DOCKER_COMPOSE

    # Create docker-compose.yaml link for compatibility
    if [ -f "docker-compose.yml" ] && [ ! -f "docker-compose.yaml" ]; then
        ln -sf docker-compose.yml docker-compose.yaml
    fi
}

check_docker() {
    log "Checking for Docker..."

    # Check if docker command exists
    if command -v docker >/dev/null 2>&1; then
        log "Docker command found, checking service..."

        # Check if docker service exists
        if systemctl list-unit-files | grep -q docker.service; then
            # Service exists, check if it's running
            if systemctl is-active --quiet docker; then
                log_success "Docker is installed and running"
            else
                log "Docker service found but not running. Starting..."
                systemctl start docker
                systemctl enable docker
                sleep 2

                if systemctl is-active --quiet docker; then
                    log_success "Docker service started"
                else
                    log_error "Failed to start Docker service. Check 'systemctl status docker'"
                    exit 1
                fi
            fi
        else
            log_warning "Docker command exists but service unit not found. Reinstalling..."
            install_docker
        fi
    else
        log "Docker not found, installing..."
        install_docker
    fi

    # Verify Docker works by running a test container
    log "Verifying Docker installation..."
    if docker run --rm hello-world >/dev/null 2>&1; then
        log_success "Docker verified working"
    else
        log_error "Docker installation verification failed. Is the daemon running?"
        exit 1
    fi

    # Check and set up Docker Compose
    setup_docker_compose

    log "Docker environment summary:"
    log "  - Docker:        $(docker --version)"
    if [ -n "$DOCKER_COMPOSE" ]; then
        log "  - Docker Compose: $($DOCKER_COMPOSE --version 2>/dev/null || echo 'version unknown')"
    else
        log "  - Docker Compose: Not available"
    fi

    return 0
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
    log "Creating Dockerfile with RHEL compatibility..."
    
    cat > Dockerfile << 'DOCKERFILEEOF'
# RHEL 9 Terraform LLM Assistant - Complete Container
FROM registry.access.redhat.com/ubi9/python-39:latest

ENV OLLAMA_HOST=0.0.0.0
ENV OLLAMA_ORIGINS=*
ENV PYTHONUNBUFFERED=1

WORKDIR /app

USER root

# Install system dependencies - handle package conflicts
RUN dnf update -y && \
    dnf install --allowerasing -y \
    procps-ng \
    wget \
    curl \
    tar \
    gzip \
    && dnf clean all

# Install Ollama
RUN curl -fsSL https://ollama.ai/install.sh > /tmp/ollama_install.sh && \
    chmod +x /tmp/ollama_install.sh && \
    sh /tmp/ollama_install.sh && \
    rm -f /tmp/ollama_install.sh

# Copy application files
COPY app/ ./

# Create directories
RUN mkdir -p /app/data /root/.ollama && \
    chmod 755 /app/entrypoint.sh

# Create CLI wrapper
RUN echo '#!/bin/bash\ncd /app\npython3 terraform_llm_assistant.py "$@"' > /usr/local/bin/terraform-llm && \
    chmod +x /usr/local/bin/terraform-llm

EXPOSE 5000 11434
VOLUME ["/root/.ollama", "/app/data"]

# Simple health check
HEALTHCHECK CMD curl -f http://localhost:11434/ || exit 1

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
    
    # Create storage directories
    mkdir -p "${INSTALL_DIR}/models" "${INSTALL_DIR}/data"

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
      - ${INSTALL_DIR}/models:/root/.ollama
      - ${INSTALL_DIR}/data:/app/data
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
COMPOSEEOF

    # Create alternative start script for systems without docker-compose
    cat > "${INSTALL_DIR}/start.sh" << 'STARTEOF'
#!/bin/bash

# Create volumes if they don't exist
docker volume create terraform-llm-data
docker volume create terraform-llm-models

# Stop and remove any existing container with the same name
docker rm -f terraform-llm-assistant 2>/dev/null || true

# Start the container
docker run -d --name terraform-llm-assistant \
    -p 5000:5000 -p 11434:11434 \
    -v terraform-llm-data:/app/data \
    -v terraform-llm-models:/root/.ollama \
    --restart unless-stopped \
    terraform-llm-assistant:rhel9

echo "Container started. Access at http://localhost:5000"
STARTEOF

    chmod +x "${INSTALL_DIR}/start.sh"
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
                <h1>🚀 Terraform LLM Assistant</h1>
                <p>Private AI Expert for RHEL 9 Infrastructure</p>
            </div>
            <div class="rhel-badge">RHEL 9 Optimized</div>
        </div>
        
        <div class="status">✅ System Ready - RHEL 9 Terraform Assistant Online</div>
        
        <div class="examples">
            <h3>RHEL 9 Examples:</h3>
            <div class="example-buttons">
                <button class="example-btn" onclick="sendExample('S3 bucket for RHEL backups')">RHEL Backups</button>
                <button class="example-btn" onclick="sendExample('VPC for RHEL enterprise environment')">Enterprise VPC</button>
                <button class="example-btn" onclick="sendExample('RHEL 9 instances with hardening')">RHEL Instances</button>
                <button class="example-btn" onclick="sendExample('RDS for RHEL applications')">Database</button>
            </div>
        </div>
        
        <div class="chat-container">
            <div id="messages" class="messages"></div>
            <div class="input-container">
                <input type="text" id="messageInput" class="input-box" 
                       placeholder="Ask about Terraform for RHEL 9..." 
                       onkeypress="if(event.key==='Enter')sendMessage()">
                <button onclick="sendMessage()" id="sendBtn" class="send-btn">Send</button>
            </div>
        </div>
    </div>

    <script>
        function addMessage(content, isUser) {
            const messagesEl = document.getElementById('messages');
            const messageEl = document.createElement('div');
            messageEl.className = `message ${isUser ? 'user' : 'assistant'}`;
            const bubbleEl = document.createElement('div');
            bubbleEl.className = 'message-bubble';
            
            if (isUser) {
                bubbleEl.textContent = content;
            } else {
                bubbleEl.innerHTML = content.replace(/```([\\s\\S]*?)```/g, '<div class="code-block">$1</div>');
            }
            
            messageEl.appendChild(bubbleEl);
            messagesEl.appendChild(messageEl);
            messagesEl.scrollTop = messagesEl.scrollHeight;
        }
        
        function sendMessage() {
            const input = document.getElementById('messageInput');
            const message = input.value.trim();
            if (!message) return;
            
            addMessage(message, true);
            input.value = '';
            document.getElementById('sendBtn').disabled = true;
            
            fetch('/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message: message })
            })
            .then(r => r.json())
            .then(data => {
                if (data.success) {
                    addMessage(data.response, false);
                } else {
                    addMessage(`Error: ${data.error}`, false);
                }
            })
            .finally(() => {
                document.getElementById('sendBtn').disabled = false;
                input.focus();
            });
        }
        
        function sendExample(text) {
            document.getElementById('messageInput').value = text;
            sendMessage();
        }
        
        setTimeout(() => {
            addMessage('Hello! Ready to help with Terraform and AWS for RHEL 9 environments.', false);
        }, 500);
        
        document.getElementById('messageInput').focus();
    </script>
</body>
</html>'''

@app.route('/api/chat', methods=['POST'])
def chat():
    try:
        data = request.get_json()
        message = data['message'].strip()
        if not message:
            return jsonify({'success': False, 'error': 'Empty message'})
        
        docs = llm_assistant.search_knowledge_base(message)
        start_time = time.time()
        response = llm_assistant.generate_response(message, docs)
        response_time = round(time.time() - start_time, 2)
        
        return jsonify({
            'success': True,
            'response': response,
            'response_time': response_time
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/health')
def health():
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'ollama_running': llm_assistant.check_ollama_status()
    })

if __name__ == '__main__':
    llm_assistant.setup_models()
    app.run(host='0.0.0.0', port=5000, debug=False)
FLASKEOF

    log_success "Flask web interface created"
}

create_entrypoint() {
    log "Creating container entrypoint..."
    
    cat > app/entrypoint.sh << 'ENTRYPOINTEOF'
#!/bin/bash
set -e

echo "🚀 Starting Terraform LLM Assistant for RHEL 9"
echo "============================================="

# Start Ollama server
echo "🦙 Starting Ollama server..."
export OLLAMA_HOST=0.0.0.0
ollama serve &
OLLAMA_PID=$!

# Wait for Ollama
echo "⏳ Waiting for Ollama..."
for i in {1..60}; do
    if curl -f -s http://localhost:11434/api/tags > /dev/null; then
        echo "✅ Ollama ready!"
        break
    fi
    sleep 2
done

# Model management
MODEL_NAME=${MODEL_NAME:-codellama:13b-instruct}
echo "🔍 Checking for model: $MODEL_NAME"

if ollama list | grep -q "$MODEL_NAME"; then
    echo "✅ Model available"
else
    echo "📥 Downloading $MODEL_NAME (this may take 5-20 minutes)..."
    timeout 3600 ollama pull "$MODEL_NAME" || echo "⚠️  Download failed, continuing..."
fi

# Initialize system
echo "🔧 Initializing knowledge base..."
python3 /app/terraform_llm_assistant.py --setup-only || echo "⚠️  Setup warnings"

echo "🌐 Starting web interface on port 5000..."

# Graceful shutdown
trap 'echo "🛑 Shutting down..."; kill $OLLAMA_PID 2>/dev/null || true; exit 0' SIGTERM SIGINT

# Start Flask
exec python3 /app/flask_web_app.py
ENTRYPOINTEOF

    chmod +x app/entrypoint.sh
    log_success "Container entrypoint created"
}

create_management_scripts() {
    log "Creating management scripts..."
    
    # Build script
    cat > build.sh << 'BUILDEOF'
#!/bin/bash
echo "🔨 Building Terraform LLM Assistant for RHEL 9..."
docker build -t terraform-llm-assistant:rhel9 .
if [ $? -eq 0 ]; then
    echo "✅ Build successful!"
else
    echo "❌ Build failed!"
    exit 1
fi
BUILDEOF

    # Start script
    cat > start.sh << STARTEOF
#!/bin/bash
echo "🚀 Starting Terraform LLM Assistant..."

if docker ps | grep -q ${PROJECT_NAME}; then
    echo "⚠️  Already running! Web: http://localhost:${WEB_PORT}"
    exit 0
fi

docker-compose up -d
if [ \$? -eq 0 ]; then
    echo "✅ Started! Web interface: http://localhost:${WEB_PORT}"
else
    echo "❌ Failed to start!"
    exit 1
fi
STARTEOF

    # Stop script with Docker Compose compatibility
    cat > stop.sh << 'STOPEOF'
#!/bin/bash
echo "🛑 Stopping..."

# Detect available Docker Compose command
if command -v docker-compose &>/dev/null; then
    COMPOSE_CMD="docker-compose"
    echo "Using standalone docker-compose"
elif docker compose version &>/dev/null; then
    COMPOSE_CMD="docker compose"
    echo "Using Docker Compose plugin"
else
    COMPOSE_CMD=""
    echo "⚠️  Docker Compose not found, using direct Docker commands"
fi

# Stop the container
if [ -n "$COMPOSE_CMD" ]; then
    echo "Stopping with $COMPOSE_CMD..."
    $COMPOSE_CMD down
    if [ $? -eq 0 ]; then
        echo "✅ Stopped!"
        exit 0
    else
        echo "⚠️  Failed to stop with Docker Compose, trying direct method..."
    fi
fi

# If Docker Compose failed or isn't available, use direct docker command
echo "Stopping with direct Docker commands..."
docker stop terraform-llm-assistant 2>/dev/null || true
docker rm terraform-llm-assistant 2>/dev/null || true

echo "✅ Stopped!"
STOPEOF

    # Status script
    cat > status.sh << STATUSEOF
#!/bin/bash
echo "📊 Status:"
if docker ps | grep -q ${PROJECT_NAME}; then
    docker ps --filter name=${PROJECT_NAME}
    echo ""
    echo "🌐 Web: http://localhost:${WEB_PORT}"
    echo "🔧 API: http://localhost:${OLLAMA_PORT}"
else
    echo "❌ Not running - use ./start.sh"
fi
STATUSEOF

    # Logs script with Docker Compose compatibility
    cat > logs.sh << 'LOGSEOF'
#!/bin/bash

# Detect available Docker Compose command
if command -v docker-compose &>/dev/null; then
    COMPOSE_CMD="docker-compose"
elif docker compose version &>/dev/null; then
    COMPOSE_CMD="docker compose"
else
    COMPOSE_CMD=""
fi

# Get logs
if [ -n "$COMPOSE_CMD" ]; then
    if [ "$1" = "-f" ]; then
        $COMPOSE_CMD logs -f terraform-llm
    else
        $COMPOSE_CMD logs --tail=50 terraform-llm
    fi
else
    # Direct Docker commands as fallback
    if [ "$1" = "-f" ]; then
        docker logs -f terraform-llm-assistant
    else
        docker logs --tail=50 terraform-llm-assistant
    fi
fi
LOGSEOF

    # CLI script
    cat > cli.sh << CLIEOF
#!/bin/bash
echo "🖥️  Accessing CLI..."
docker exec -it ${PROJECT_NAME} terraform-llm
CLIEOF

    # Cleanup script with Docker Compose compatibility
    cat > cleanup.sh << 'CLEANUPEOF'
#!/bin/bash
echo "🧹 Cleanup - removes everything!"
read -p "Type 'yes' to confirm: " confirm
if [ "$confirm" = "yes" ]; then
    # Detect available Docker Compose command
    if command -v docker-compose &>/dev/null; then
        COMPOSE_CMD="docker-compose"
    elif docker compose version &>/dev/null; then
        COMPOSE_CMD="docker compose"
    else
        COMPOSE_CMD=""
    fi

    # Stop containers with Docker Compose if available
    if [ -n "$COMPOSE_CMD" ]; then
        echo "Stopping containers with $COMPOSE_CMD..."
        $COMPOSE_CMD down || true
    else
        echo "Stopping containers with direct Docker commands..."
        docker stop terraform-llm-assistant 2>/dev/null || true
        docker rm terraform-llm-assistant 2>/dev/null || true
    fi

    # Remove images and volumes
    echo "Removing Docker image..."
    docker rmi terraform-llm-assistant:rhel9 -f || true

    echo "Removing Docker volumes..."
    docker volume rm terraform-llm-data terraform-llm-models 2>/dev/null || true
    docker volume prune -f

    echo "✅ Cleanup complete!"
else
    echo "❌ Cancelled"
fi
CLEANUPEOF

    chmod +x *.sh
    log_success "Management scripts created"
}

create_systemd_service() {
    log "Creating systemd service..."
    
    # Determine the right Docker Compose command to use in the service
    local docker_compose_cmd
    if [ "$DOCKER_COMPOSE" = "docker compose" ]; then
        docker_compose_cmd="/usr/bin/docker compose"
    elif [ "$DOCKER_COMPOSE" = "docker-compose" ]; then
        docker_compose_cmd="/usr/bin/docker-compose"
    else
        # Fallback to using start.sh script which doesn't require compose
        docker_compose_cmd="${INSTALL_DIR}/start.sh"
        log_warning "Using start.sh script in systemd service (Docker Compose not available)"
    fi

    # Create the service file with the appropriate command
    if [ "$docker_compose_cmd" = "${INSTALL_DIR}/start.sh" ]; then
        cat > /etc/systemd/system/terraform-llm.service << EOF
[Unit]
Description=Terraform LLM Assistant
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=${INSTALL_DIR}
ExecStart=${INSTALL_DIR}/start.sh
ExecStop=docker stop ${PROJECT_NAME} && docker rm ${PROJECT_NAME}
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
EOF
    else
        cat > /etc/systemd/system/terraform-llm.service << EOF
[Unit]
Description=Terraform LLM Assistant
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=${INSTALL_DIR}
ExecStart=${docker_compose_cmd} up -d
ExecStop=${docker_compose_cmd} down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
EOF
    fi

    systemctl daemon-reload
    systemctl enable terraform-llm.service
    log_success "Systemd service created"
}

    # Function to check service status
    service_status() {
    log "Checking service status..."

    # Check if container exists and is running
    if docker ps | grep -q ${PROJECT_NAME}; then
        log_success "Container is running"

        # Show container details
        docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" -f name=${PROJECT_NAME}

        # Check web service
        if curl -s http://localhost:${WEB_PORT}/health > /dev/null 2>&1; then
            log_success "Web interface responsive at http://localhost:${WEB_PORT}"

            # Get health details
            local health_json=$(curl -s http://localhost:${WEB_PORT}/health)
            echo "Health details:"
            echo "$health_json" | sed 's/^/    /'
        else
            log_warning "Web interface not responding at http://localhost:${WEB_PORT}"
        fi

        # Check Ollama API
        if curl -s http://localhost:${OLLAMA_PORT}/api/tags > /dev/null 2>&1; then
            log_success "Ollama API responsive at http://localhost:${OLLAMA_PORT}"

            # Get model details
            local model_json=$(curl -s http://localhost:${OLLAMA_PORT}/api/tags)
            echo "Models loaded:"
            echo "$model_json" | grep -o '"name":"[^"]*"' | sed 's/^/    /'
        else
            log_warning "Ollama API not responding at http://localhost:${OLLAMA_PORT}"
        fi

        # Show recent logs
        log "Recent container logs:"
        docker logs ${PROJECT_NAME} --tail 10
    else
        log_error "Container ${PROJECT_NAME} is not running"

        # Check if it exists but is stopped
        if docker ps -a | grep -q ${PROJECT_NAME}; then
            log_warning "Container exists but is stopped"
            log "Container details:"
            docker ps -a --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" -f name=${PROJECT_NAME}
            log "Start with: docker start ${PROJECT_NAME}"
        else
            log_error "Container does not exist"
            log "Please run the deployment script again"
        fi
    fi

    # Check systemd service if applicable
    if systemctl list-unit-files | grep -q terraform-llm.service; then
        log "Systemd service status:"
        systemctl status terraform-llm.service --no-pager | head -n 15
    fi
    }

build_and_start() {
    log "Building and starting..."
    
    cd "${INSTALL_DIR}"
    log "Working directory: $(pwd)"

    # List files to ensure everything is in place
    log "Checking project files:"
    ls -la

    # Check for container conflicts before building
    if docker ps -a | grep -q "${PROJECT_NAME}"; then
        log_warning "Container ${PROJECT_NAME} already exists"

        if docker ps | grep -q "${PROJECT_NAME}"; then
            log_warning "Container is currently running"
        fi

        log "Removing existing container to avoid conflicts"
        if ! docker rm -f "${PROJECT_NAME}" 2>/dev/null; then
            log_error "Failed to remove existing container. Please run manually: docker rm -f ${PROJECT_NAME}"
            exit 1
        fi
        log_success "Removed existing container"
    fi

    log "Building Docker image..."
    if ! docker build -t terraform-llm-assistant:rhel9 .; then
        log_error "Build failed"
        exit 1
    fi

    # Verify the image was created
    log "Verifying Docker image:"
    docker images | grep terraform-llm-assistant || {
        log_error "Image not found after build"
        exit 1
    }

    # Use Docker Compose if available, with proper error handling
    if [ -n "$DOCKER_COMPOSE" ]; then
        log "Using ${DOCKER_COMPOSE} to start container"

        # Check if the Docker Compose file exists
        if [ ! -f "docker-compose.yml" ] && [ ! -f "docker-compose.yaml" ]; then
            log_error "Docker Compose file not found in $(pwd)"
            ls -la
            log "Trying with direct docker commands..."
            start_with_docker
            return
        fi

        # Run Docker Compose with detailed error logging
        if $DOCKER_COMPOSE up -d; then
            log_success "Container started with ${DOCKER_COMPOSE}"
        else
            COMPOSE_EXIT_CODE=$?
            log_error "Start with ${DOCKER_COMPOSE} failed (exit code: ${COMPOSE_EXIT_CODE})"
            log "Checking Docker Compose configuration..."
            $DOCKER_COMPOSE config || log_error "Docker Compose configuration is invalid"

            log "Trying with direct docker commands..."
            start_with_docker
        fi
    else
        log "Docker Compose not available, using direct docker commands"
        start_with_docker
    fi

    # Verify container is running and perform comprehensive checks
    verify_container_running
    }

    # Function to start container with plain docker
    start_with_docker() {
        log "Starting container with direct Docker commands"

        # Create volumes if they don't exist
        log "Creating Docker volumes"
        docker volume create terraform-llm-data
        docker volume create terraform-llm-models

        # Check for and remove any existing container with the same name
        if docker ps -a | grep -q "${PROJECT_NAME}"; then
            log "Removing existing container ${PROJECT_NAME}"
            if ! docker rm -f "${PROJECT_NAME}" 2>/dev/null; then
                log_warning "Failed to remove existing container automatically"
                log "Attempting forced removal"
                docker rm -f "${PROJECT_NAME}" 2>/dev/null || true
                sleep 2
            fi
        fi

        # Start the container using docker directly
        log "Starting container: ${PROJECT_NAME}"
        if ! docker run -d --name ${PROJECT_NAME} \
             -p ${WEB_PORT}:5000 -p ${OLLAMA_PORT}:11434 \
             -v terraform-llm-data:/app/data \
             -v terraform-llm-models:/root/.ollama \
             --restart unless-stopped \
             terraform-llm-assistant:rhel9; then
            log_error "Start with docker failed"
            log "Check if ports ${WEB_PORT} and ${OLLAMA_PORT} are already in use"
            log "Try: netstat -tulpn | grep -E '${WEB_PORT}|${OLLAMA_PORT}'"
            exit 1
        fi

        log "Container started with ID: $(docker ps -q -f name=${PROJECT_NAME})"
    }

    # Function to verify container is running properly
    verify_container_running() {
        log "Verifying container status..."

        # Check if container exists
        if ! docker ps | grep -q ${PROJECT_NAME}; then
            log_error "Container not found in running containers"
            log "Container logs:"
            docker logs ${PROJECT_NAME} 2>&1 || log_error "Could not get logs"
            exit 1
        fi

        log_success "Container running"
        log "Container details:"
        docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" -f name=${PROJECT_NAME}

        # Check if ports are actually bound and accessible
        log "Checking port bindings..."
        if ! docker port ${PROJECT_NAME} | grep -q ${WEB_PORT}; then
            log_warning "Web port ${WEB_PORT} may not be properly bound"
        else
            log_success "Port ${WEB_PORT} bound correctly"
        fi

        # Check container logs for any issues
        log "Initial container logs:"
        docker logs ${PROJECT_NAME} --tail 20

        # Wait for web service to be ready (up to 30 seconds)
        log "Waiting for web service to be ready..."
        web_ready=false
        for i in $(seq 1 30); do
            if curl -s http://localhost:${WEB_PORT}/health > /dev/null 2>&1; then
                log_success "Web interface responding at http://localhost:${WEB_PORT}"
                web_ready=true
                break
            elif [ $i -eq 30 ]; then
                log_warning "Web interface not responding after 30 seconds, but container is running"
                log "This could indicate the container is still initializing"
                log "You can check status later with: curl http://localhost:${WEB_PORT}/health"
            else
                echo -n "."
                sleep 1
            fi
        done

        # Check if Ollama API is responding and wait for model download to complete
        log "Checking Ollama status and model availability..."
        ollama_ready=false
        if curl -s http://localhost:${OLLAMA_PORT}/api/tags > /dev/null 2>&1; then
            log_success "Ollama API responding at http://localhost:${OLLAMA_PORT}"
            ollama_ready=true
        else
            log_warning "Ollama API not yet responding at http://localhost:${OLLAMA_PORT}"
            log "Waiting for Ollama to initialize (up to 2 minutes)..."

            # Wait for Ollama API to become available (up to 2 minutes)
            for i in $(seq 1 24); do
                if curl -s http://localhost:${OLLAMA_PORT}/api/tags > /dev/null 2>&1; then
                    log_success "Ollama API is now responding"
                    ollama_ready=true
                    break
                else
                    echo -n "."
                    sleep 5
                fi
            done

            if [ "$ollama_ready" = false ]; then
                log_warning "Ollama API still not responding after 2 minutes"
                log "Container will continue initialization in background"
            fi
        fi

        # If Ollama is ready, check for LLM model download status
        if [ "$ollama_ready" = true ]; then
            log "Checking LLM model download status..."
            model_name="codellama:${MODEL_SIZE}-instruct"
            model_ready=false

            # First check if model is already available
            model_check=$(curl -s http://localhost:${OLLAMA_PORT}/api/tags | grep -o "\"${model_name}\"")
            if [ -n "$model_check" ]; then
                log_success "LLM model ${model_name} is already downloaded and ready"
                model_ready=true
            else
                log "LLM model ${model_name} is being downloaded. This may take 5-20 minutes..."
                log "Waiting for model download to complete (checking every 30 seconds)..."
                log "Press Ctrl+C to continue in background if this is taking too long"

                # Check every 30 seconds for model availability (up to 30 minutes)
                for i in $(seq 1 60); do
                    model_check=$(curl -s http://localhost:${OLLAMA_PORT}/api/tags | grep -o "\"${model_name}\"")
                    if [ -n "$model_check" ]; then
                        log_success "LLM model ${model_name} download completed!"
                        model_ready=true
                        break
                    else
                        # Show some download progress if available in logs
                        download_progress=$(docker logs --tail 10 ${PROJECT_NAME} 2>&1 | grep -i "download" | tail -1)
                        if [ -n "$download_progress" ]; then
                            log "Progress: $download_progress"
                        else
                            echo -n "."
                        fi
                        sleep 30
                    fi
                done

                if [ "$model_ready" = false ]; then
                    log_warning "Model download still in progress after waiting 30 minutes"
                    log "The download will continue in the background"
                    log "Check status later with: docker logs ${PROJECT_NAME}"
                fi
            fi
        fi

        log ""
        log "📋 Summary:"
        log "   - Container: ${PROJECT_NAME}"
        log "   - Web UI:    http://localhost:${WEB_PORT}"
        log "   - Ollama:    http://localhost:${OLLAMA_PORT}"
        if [ "$web_ready" = true ] && [ "$model_ready" = true ]; then
            log "   - Status:    ✅ READY - All services initialized"
        elif [ "$web_ready" = true ] && [ "$ollama_ready" = true ]; then
            log "   - Status:    ⚠️  INITIALIZING - Model download in progress"
        else
            log "   - Status:    ⚠️  STARTING - Services initializing"
        fi
        log "   - Logs:      docker logs ${PROJECT_NAME} -f"
        log ""

        if [ "$model_ready" = false ]; then
            log "⚠️  The LLM model is still downloading or initializing"
            log "📝 This can take 5-30 minutes depending on your internet connection"
            log "📊 Monitor progress with: docker logs -f ${PROJECT_NAME}"
        else
            log "✅ System is fully initialized and ready to use!"
        fi
    }
    
    log_success "Container running"
    
    # Health check
    sleep 10
    if curl -f -s http://localhost:${WEB_PORT}/health > /dev/null; then
        log_success "Web interface healthy at http://localhost:${WEB_PORT}"
    else
        log_warning "Web interface starting up..."
    fi

# Create README file
create_readme() {
    log "Creating README file..."

    cat > "${INSTALL_DIR}/README.md" << 'READMEEOF'
# Terraform LLM Assistant for RHEL

This is an AI-powered assistant for working with Terraform, designed to run on RHEL/Enterprise Linux.

## Management Scripts

* `./start.sh` - Start the container
* `./stop.sh` - Stop the container
* `./logs.sh` - View logs from the running container
* `./status.sh` - Check the status of the container
* `./cleanup.sh` - Remove all container artifacts

## Container Management

### Starting the Container

```bash
# Using the convenience script
./start.sh

# Alternatively with Docker Compose
docker-compose up -d
# or
docker compose up -d

# Direct Docker method
docker start terraform-llm-assistant
```

### Stopping the Container

```bash
# Using the convenience script
./stop.sh

# Alternatively with Docker Compose
docker-compose down
# or
docker compose down

# Direct Docker methods
docker stop terraform-llm-assistant
# To remove container as well
docker rm terraform-llm-assistant
```

### Checking Container Status

```bash
# View running containers
docker ps

# View all containers (including stopped)
docker ps -a

# Check logs
./logs.sh
# or
docker logs terraform-llm-assistant
# For continuous log viewing
docker logs -f terraform-llm-assistant
```

## System Service

A systemd service has been created to manage the container:

```bash
systemctl start terraform-llm    # Start the service
systemctl stop terraform-llm     # Stop the service
systemctl status terraform-llm   # Check status
```

## Web Interface

Access the web interface at: http://localhost:5000
Ollama API available at: http://localhost:11434

## Troubleshooting

If you encounter issues:

1. Check container status: `docker ps -a | grep terraform-llm-assistant`
2. View container logs: `./logs.sh -f` or `docker logs terraform-llm-assistant`
3. Restart the container: `./stop.sh && ./start.sh`
4. Check systemd service status: `systemctl status terraform-llm`
5. Ensure ports 5000 and 11434 are not in use by other applications
6. If the container fails to start, check disk space: `df -h`

### Complete Container Removal

If you need to remove the container completely and start fresh:

```bash
# Stop and remove container
docker stop terraform-llm-assistant
docker rm terraform-llm-assistant

# Remove image
docker rmi terraform-llm-assistant:rhel9

# Remove volumes (will delete all data!)
docker volume rm terraform-llm-data terraform-llm-models

# Or use the cleanup script
./cleanup.sh
```
READMEEOF

    log "✅ README file created"
}

main() {
    echo "🚀 RHEL 9 Terraform LLM Assistant Deployment"
    echo "============================================="
    
    read -p "Continue? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 0
    fi

    # Check for running LLM containers
    if docker ps | grep -i "llm\|ollama\|llama\|language-model" > /dev/null; then
        echo "⚠️  Found running LLM/Ollama containers:"
        docker ps --format "table {{.Names}}\t{{.Image}}\t{{.Status}}" | grep -i "llm\|ollama\|llama\|language-model"
        echo ""

        read -p "📋 Stop these containers and continue? (y/N): " -n 1 -r
        echo ""
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            echo "❌ Exiting at user request"
            exit 0
        else
            echo "🛑 Stopping containers..."
            docker ps --format "{{.Names}}" | grep -i "llm\|ollama\|llama\|language-model" | xargs -r docker stop
            echo "✅ Containers stopped"
        fi
    fi
    
    check_rhel_version
    check_root
    check_system_requirements
    check_docker
    
    create_project_structure
    create_dockerfile
    create_docker_compose
    create_llm_assistant
    create_flask_web_app
    create_entrypoint
    create_management_scripts
        create_readme
    create_systemd_service
    
    read -p "🔨 Build and start now? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        build_and_start
        echo ""
        echo "🎉 Installation complete!"
        echo "📁 Files location: ${INSTALL_DIR}"
        echo ""
        echo "🔍 For detailed status: $0 status"
        echo "📊 Web interface: http://localhost:${WEB_PORT} (may take time to initialize)"
        echo "📝 View logs: docker logs ${PROJECT_NAME} -f"
        echo "🔄 Restart if needed: cd ${INSTALL_DIR} && ./stop.sh && ./start.sh"
        echo ""
        echo "⏳ Note: First startup may take 5-20 minutes to download the model"
    else
        echo "✅ Setup complete! Run: cd ${INSTALL_DIR} && ./build.sh && ./start.sh"
    fi
}

# Command to execute
COMMAND="install" # Default command

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        status)
            COMMAND="status"
            shift
            ;;
        --model-size) MODEL_SIZE="$2"; shift 2 ;;
        --web-port) WEB_PORT="$2"; shift 2 ;;
        --install-dir) INSTALL_DIR="$2"; shift 2 ;;
        --help|-h)
            echo "RHEL 9 Terraform LLM Assistant"
            echo "Usage:"
            echo "  $0 [options]                    Install the assistant"
            echo "  $0 status                       Check service status"
            echo ""
            echo "Options:"
            echo "  --model-size 7b|13b|34b         Model size (default: 13b)"
            echo "  --web-port PORT                Web interface port (default: 5000)"
            echo "  --install-dir DIR               Installation directory"
            echo "  --help, -h                      Show this help message"
            exit 0
            ;;
        *) log_error "Unknown option: $1"; exit 1 ;;
    esac
done

# Validate inputs
if [[ ! "$MODEL_SIZE" =~ ^(7b|13b|34b)$ ]]; then
    log_error "Invalid model size: $MODEL_SIZE"
    exit 1
fi

# Execute the appropriate command with error handling
case "$COMMAND" in
    status)
        log "Checking service status..."
        service_status
        STATUS_EXIT=$?
        if [ $STATUS_EXIT -ne 0 ]; then
            log_error "Status check failed with exit code $STATUS_EXIT"
            exit $STATUS_EXIT
        fi
        ;;
    install)
        log "Starting installation..."
        main "$@"
        INSTALL_EXIT=$?
        if [ $INSTALL_EXIT -ne 0 ]; then
            log_error "Installation failed with exit code $INSTALL_EXIT"
            log "Check the logs above for errors"
            log "For detailed container logs, run: docker logs ${PROJECT_NAME}"
            exit $INSTALL_EXIT
        fi
        ;;
esac

log "Command completed successfully"