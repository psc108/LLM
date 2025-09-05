#!/bin/bash
set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log() {
    echo -e "${BLUE}[$(date +'%H:%M:%S')]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[$(date +'%H:%M:%S')] ✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}[$(date +'%H:%M:%S')] ⚠️ $1${NC}"
}

# Setup virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    log "Creating Python virtual environment..."
    python3 -m venv venv
    log_success "Virtual environment created"

    log "Installing dependencies..."
    source venv/bin/activate
    pip install --upgrade pip

    if [ -f "requirements.txt" ]; then
        pip install -r requirements.txt
    else
        pip install flask==2.3.3 requests==2.31.0 python-dotenv==1.0.0 Werkzeug==2.3.7
    fi
    log_success "Dependencies installed"
fi

# Activate virtual environment
source venv/bin/activate

# Load environment variables from .env
if [ -f ".env" ]; then
    export $(grep -v '^#' .env | xargs)
fi

# Create necessary directories
log "Ensuring data directories exist..."
mkdir -p "${DATA_DIR:-~/terraform-llm-assistant/data}"
mkdir -p "${LOGS_DIR:-~/terraform-llm-assistant/logs}"

# Check if Ollama is installed
if ! command -v ollama &> /dev/null; then
    log_warning "Ollama is not installed. Attempting to install..."
    curl -fsSL https://ollama.ai/install.sh | sh
    if [ $? -ne 0 ]; then
        log_warning "Failed to install Ollama automatically. Please install it manually:"
        log_warning "curl -fsSL https://ollama.ai/install.sh | sh"
        exit 1
    fi
    log_success "Ollama installed successfully"
fi

# Start Ollama service
log "Starting Ollama service..."
if ! pgrep -f "ollama serve" > /dev/null; then
    # Start Ollama in the background
    nohup ollama serve > "${LOGS_DIR:-logs}/ollama.log" 2>&1 &
    sleep 3
    log_success "Ollama service started"
else
    log_success "Ollama service already running"
fi

# Check for model and pull if needed
log "Checking if model is available..."
if ! ollama list | grep -q "${MODEL_NAME:-codellama:13b-instruct}"; then
    log "Downloading model: ${MODEL_NAME:-codellama:13b-instruct}"
    log "This may take some time depending on your internet connection."
    ollama pull "${MODEL_NAME:-codellama:13b-instruct}"
    log_success "Model downloaded successfully"
else
    log_success "Model is already available"
fi

# Start Flask application
log "Starting Flask application..."
log_success "Terraform LLM Assistant will be available at: http://${HOST:-localhost}:${PORT:-5000}"

# Use native_app.py if available, otherwise use app.py
if [ -f "app/native_app.py" ]; then
    python app/native_app.py
elif [ -f "app/app.py" ]; then
    python app/app.py
else
    log_warning "No app file found in the app directory."
    exit 1
fi
