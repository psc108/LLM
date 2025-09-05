#!/bin/bash
set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

log() {
    echo -e "${BLUE}[$(date +'%H:%M:%S')]${NC} $1"
}

log_error() {
    echo -e "${RED}[$(date +'%H:%M:%S')] ❌ $1${NC}"
}

log_success() {
    echo -e "${GREEN}[$(date +'%H:%M:%S')] ✅ $1${NC}"
}

log "=== Flask Application Debug Tool ==="

# Navigate to the application directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/new-app" || { log_error "Cannot find application directory"; exit 1; }

log "Current directory: $(pwd)"

# Check if venv exists
if [ -d "venv" ]; then
    log_success "Virtual environment exists"
    log "Activating virtual environment..."
    source venv/bin/activate || log_error "Failed to activate virtual environment"
    log_success "Virtual environment activated"
else
    log_error "Virtual environment not found at $(pwd)/venv"
    exit 1
fi

# Check Python and packages
log "Python version:"
python --version || log_error "Python not found"

log "Checking Flask installation:"
python -c "import flask; print(f'Flask {flask.__version__} is installed')" || log_error "Flask not installed"

log "Checking required packages:"
packages=("flask" "requests" "psutil" "dotenv" "Werkzeug" "markdown" "jinja2")

for package in "${packages[@]}"; do
    python -c "import $package; print(f'{package} is installed')" || log_error "$package not installed"
done

# Check if app.py exists
if [ -f "app.py" ]; then
    log_success "app.py found"
else
    log_error "app.py not found in $(pwd)"
    ls -la
    exit 1
fi

# Check port availability
port=${PORT:-5000}
log "Checking if port $port is in use:"
if command -v lsof >/dev/null 2>&1; then
    if lsof -i :$port; then
        log_error "Port $port is already in use"
    else
        log_success "Port $port is available"
    fi
elif command -v ss >/dev/null 2>&1; then
    if ss -lntu | grep -q ":$port "; then
        log_error "Port $port is already in use"
    else
        log_success "Port $port is available"
    fi
elif command -v netstat >/dev/null 2>&1; then
    if netstat -lntu | grep -q ":$port "; then
        log_error "Port $port is already in use"
    else
        log_success "Port $port is available"
    fi
else
    log_error "Cannot check port usage: lsof, ss, and netstat not available"
fi

# Check Ollama status
log "Checking Ollama status:"
if command -v ollama >/dev/null 2>&1; then
    log_success "Ollama is installed"
    # Check if Ollama is running
    if pgrep -f "ollama serve" > /dev/null; then
        log_success "Ollama service is running"
    else
        log_error "Ollama service is not running"
    fi

    # Check available models
    log "Available models:"
    ollama list || log_error "Could not list Ollama models"
else
    log_error "Ollama is not installed"
fi

log "Starting Flask application in debug mode..."
export FLASK_DEBUG=true

# Try to start the application with verbose output
log "Attempting to start Flask application (Ctrl+C to exit):"
python -u app.py
