#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

log() {
    echo -e "${GREEN}[$(date +'%H:%M:%S')]${NC} $1"
}

log_error() {
    echo -e "${RED}[$(date +'%H:%M:%S')]${NC} $1"
}

log "Stopping Terraform LLM Assistant..."

# Stop Flask application
pkill -f "python.*app\.py" && log "Flask application stopped" || log_error "Flask application not running"

# Ask if user wants to stop Ollama too
read -p "Do you want to stop the Ollama service too? (y/N): " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    # Stop Ollama service
    pkill -f "ollama serve" && log "Ollama service stopped" || log_error "Ollama service not running"
fi

log "Terraform LLM Assistant stopped"
