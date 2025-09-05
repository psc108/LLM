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

# Navigate to the application directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/new-app" || { echo "Error: Cannot find application directory at $SCRIPT_DIR/new-app"; exit 1; }

log "Current directory: $(pwd)"

# Setup virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    log "Creating Python virtual environment in new-app..."
    python3 -m venv venv
    log_success "Virtual environment created"
fi

# Activate virtual environment
log "Activating virtual environment..."
source venv/bin/activate

# Install/update dependencies
log "Installing dependencies..."
pip install --upgrade pip

if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
else
    pip install flask==2.3.3 requests==2.31.0 python-dotenv==1.0.0 Werkzeug==2.3.7
fi

log_success "Dependencies installed"

# Load environment variables from .env
if [ -f ".env" ]; then
    # Use grep to exclude comments and empty lines
    export $(grep -v '^#' .env | grep -v '^$' | xargs) 2>/dev/null || true
fi

# Set default loading timeout if not specified in .env
export LOADING_TIMEOUT=${LOADING_TIMEOUT:-20000}

# Create necessary directories with path expansion
log "Ensuring data directories exist..."
DATA_DIR_EXPANDED=$(eval echo "${DATA_DIR:-~/terraform-llm-assistant/data}")
LOGS_DIR_EXPANDED=$(eval echo "${LOGS_DIR:-~/terraform-llm-assistant/logs}")

# Create directories with proper expansion
mkdir -p "$DATA_DIR_EXPANDED"
mkdir -p "$LOGS_DIR_EXPANDED"
mkdir -p "logs"

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
    nohup ollama serve > "$LOGS_DIR_EXPANDED/ollama.log" 2>&1 &
    sleep 3
    log_success "Ollama service started"
else
    log_success "Ollama service already running"
fi

# Check for model and pull if needed
log "Checking if model is available..."
MODEL_TO_USE="${MODEL_NAME:-codellama:13b-instruct}"

# Use a more precise match to check for the model
MODEL_AVAILABLE=false
if ollama list | grep -q "^$MODEL_TO_USE\s"; then
    MODEL_AVAILABLE=true
fi

if [ "$MODEL_AVAILABLE" = false ]; then
    log "Downloading model: $MODEL_TO_USE"
    log "This may take some time depending on your internet connection."
    log "You'll see progress information in the app interface."
    log "================================================================="
    log "DOWNLOADING: $MODEL_TO_USE"
    log "================================================================="
    ollama pull "$MODEL_TO_USE"
    log_success "================================================================="
    log_success "Model $MODEL_TO_USE downloaded successfully"
    log_success "================================================================="
else
    log_success "Model $MODEL_TO_USE is already available"
fi

# Verify model is fully loaded before starting Flask
log "Verifying model is ready..."
MAX_RETRIES=5
RETRY_COUNT=0
MODEL_READY=false

while [ $RETRY_COUNT -lt $MAX_RETRIES ] && [ "$MODEL_READY" = false ]; do
    if ollama list | grep -q "${MODEL_NAME:-codellama:13b-instruct}"; then
        log_success "Model ${MODEL_NAME:-codellama:13b-instruct} is ready"
        MODEL_READY=true
    else
        RETRY_COUNT=$((RETRY_COUNT+1))
        log "Waiting for model to be fully loaded (attempt $RETRY_COUNT/$MAX_RETRIES)..."
        sleep 3
    fi
done

# Start Flask application
log "Starting Flask application..."
log_success "Terraform LLM Assistant will be available at: http://${HOST:-localhost}:${PORT:-5000}"

# Export a variable for the loading screen timeout
# This ensures the loading screen gets removed even if there's a delay in model loading
export LOADING_TIMEOUT=${LOADING_TIMEOUT:-30000}
log "Setting loading screen timeout to ${LOADING_TIMEOUT}ms"

# Check if app.py exists and run it
if [ -f "app.py" ]; then
    # Ensure we're using the virtual environment's Python
    if [ -f "venv/bin/python" ]; then
        log "Using virtual environment Python to start application"
        venv/bin/python app.py
    else
        log "Virtual environment Python not found, using system Python"
        python3 app.py
    fi
else
    log_warning "No app.py found in $(pwd)"
    ls -la
    exit 1
fi