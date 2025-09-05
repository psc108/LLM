#!/usr/bin/env bash
set -euo pipefail

# Configuration
PROJECT_NAME="terraform-llm-assistant"
INSTALL_DIR="${INSTALL_DIR:-$HOME/terraform-llm-assistant}"
DATA_DIR="${DATA_DIR:-$INSTALL_DIR/data}"
WEB_PORT="${WEB_PORT:-5000}"
OLLAMA_PORT="${OLLAMA_PORT:-11434}"
MODEL_SIZE="${MODEL_SIZE:-13b}"
PYTHON_CMD="${PYTHON_CMD:-python3}"
VENV_DIR="${VENV_DIR:-$INSTALL_DIR/venv}"

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

log_header() {
    echo -e "${CYAN}=======================================================${NC}"
    echo -e "${CYAN}== $1${NC}"
    echo -e "${CYAN}=======================================================${NC}"
}

# Check if port is in use
port_in_use() {
    local port=$1
    if command -v nc >/dev/null 2>&1; then
        nc -z localhost "$port" >/dev/null 2>&1
        return $?
    elif command -v ss >/dev/null 2>&1; then
        ss -tulpn | grep -q ":$port "
        return $?
    elif command -v lsof >/dev/null 2>&1; then
        lsof -i:"$port" >/dev/null 2>&1
        return $?
    elif command -v netstat >/dev/null 2>&1; then
        netstat -tulpn 2>/dev/null | grep -q ":$port "
        return $?
    else
        return 1
    fi
}

# Find an available port
find_available_port() {
    local start_port=$1
    local max_tries=${2:-20}
    local port=$start_port

    for ((i=0; i<max_tries; i++)); do
        if ! port_in_use "$port"; then
            echo "$port"
            return 0
        fi
        port=$((port + 1))
    done

    echo "$start_port"
    return 1
}

# Check system requirements
check_requirements() {
    log_header "Checking System Requirements"

    # Check Python
    if ! command -v "$PYTHON_CMD" >/dev/null 2>&1; then
        log_error "Python 3 not found. Please install Python 3.8+ first."
        exit 1
    fi

    local python_version=$($PYTHON_CMD -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    log_success "Python $python_version found"

    # Check pip
    if ! $PYTHON_CMD -m pip --version >/dev/null 2>&1; then
        log_error "pip not found. Please install pip for Python 3."
        exit 1
    fi
    log_success "pip found"

    # Check curl for Ollama installation
    if ! command -v curl >/dev/null 2>&1; then
        log_error "curl not found. Please install curl first."
        exit 1
    fi
    log_success "curl found"

    # Check memory requirements
    local total_memory_gb=$(free -g | awk 'NR==2{print $2}' 2>/dev/null || echo "0")
    local required_memory=8

    if [[ $MODEL_SIZE == "34b" ]]; then
        required_memory=32
    elif [[ $MODEL_SIZE == "13b" ]]; then
        required_memory=16
    fi

    if [[ $total_memory_gb -gt 0 && $total_memory_gb -lt $required_memory ]]; then
        log_warning "System has ${total_memory_gb}GB RAM, ${required_memory}GB recommended for ${MODEL_SIZE} model"
        read -p "Continue anyway? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    else
        log_success "Memory: ${total_memory_gb}GB (sufficient for ${MODEL_SIZE} model)"
    fi
}

# Install Ollama locally
install_ollama() {
    log_header "Installing Ollama"

    if command -v ollama >/dev/null 2>&1; then
        log_success "Ollama already installed"
        return 0
    fi

    log "Downloading and installing Ollama..."
    curl -fsSL https://ollama.ai/install.sh | sh

    if command -v ollama >/dev/null 2>&1; then
        log_success "Ollama installed successfully"
    else
        log_error "Failed to install Ollama"
        exit 1
    fi
}

# Setup project directories
setup_directories() {
    log_header "Setting up Project Directories"

    log "Creating directory structure..."
    mkdir -p "$INSTALL_DIR"
    mkdir -p "$DATA_DIR"
    mkdir -p "$INSTALL_DIR/logs"

    log_success "Directory structure created at: $INSTALL_DIR"
}

# Setup Python virtual environment
setup_python_env() {
    log_header "Setting up Python Environment"

    log "Creating virtual environment..."
    $PYTHON_CMD -m venv "$VENV_DIR"

    log "Activating virtual environment..."
    source "$VENV_DIR/bin/activate"

    log "Upgrading pip..."
    pip install --upgrade pip

    log "Installing Python dependencies..."
    # Install from requirements.txt if it exists, otherwise install basic requirements
    if [[ -f "requirements.txt" ]]; then
        pip install -r requirements.txt
    elif [[ -f "app/requirements.txt" ]]; then
        pip install -r app/requirements.txt
    else
        # Fallback to basic requirements
        pip install flask==2.3.3 requests==2.31.0 python-dotenv==1.0.0
    fi

    log_success "Python environment setup complete"
}

# Copy application files
copy_app_files() {
    log_header "Setting up Application Files"

    log "Copying application files..."

    # Copy the entire app directory if it exists
    if [[ -d "app" ]]; then
        cp -r app/* "$INSTALL_DIR/"
    fi

    # Copy static files and templates
    if [[ -d "app/static" ]]; then
        cp -r app/static "$INSTALL_DIR/"
    fi

    if [[ -d "app/templates" ]]; then
        cp -r app/templates "$INSTALL_DIR/"
    fi

    # Copy main application files
    for file in app.py basic_app.py minimal_app.py simple_flask_app.py api_routes.py; do
        if [[ -f "app/$file" ]]; then
            cp "app/$file" "$INSTALL_DIR/"
        fi
    done

    # Copy model_manager.py if it exists
    if [[ -f "model_manager.py" ]]; then
        cp "model_manager.py" "$INSTALL_DIR/"
    fi

    # Copy native files
    if [[ -f "app/native_config.py" ]]; then
        cp "app/native_config.py" "$INSTALL_DIR/"
    fi

    if [[ -f "app/native_app.py" ]]; then
        cp "app/native_app.py" "$INSTALL_DIR/"
        chmod +x "$INSTALL_DIR/native_app.py"
    fi

    log_success "Application files copied"
}

# Create environment configuration
create_env_config() {
    log_header "Creating Configuration"

    log "Creating environment configuration..."

    cat > "$INSTALL_DIR/.env" << EOF
# Flask Configuration
FLASK_APP=app.py
FLASK_ENV=development
FLASK_DEBUG=False
HOST=localhost
PORT=$WEB_PORT

# Ollama Configuration
OLLAMA_HOST=localhost
OLLAMA_PORT=$OLLAMA_PORT
OLLAMA_MODEL=codellama:${MODEL_SIZE}-instruct

# Data Paths
DATA_DIR=$DATA_DIR
MODELS_DIR=$DATA_DIR/models
LOGS_DIR=$INSTALL_DIR/logs

# Application Settings
PROJECT_NAME=$PROJECT_NAME
MODEL_SIZE=$MODEL_SIZE
EOF

    log_success "Configuration created"
}

# Create startup script
create_startup_script() {
    log_header "Creating Startup Scripts"

    # Create main startup script
    cat > "$INSTALL_DIR/start.sh" << 'EOF'
#!/bin/bash
set -e

# Load configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Load environment variables
if [[ -f .env ]]; then
    export $(grep -v '^#' .env | xargs)
fi

# Activate virtual environment
source venv/bin/activate

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

log() {
    echo -e "${BLUE}[$(date +'%H:%M:%S')]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[$(date +'%H:%M:%S')] ✅ $1${NC}"
}

# Start Ollama service in background
log "Starting Ollama service..."
if ! pgrep -f "ollama serve" > /dev/null; then
    nohup ollama serve > logs/ollama.log 2>&1 &
    sleep 3
    log_success "Ollama service started"
else
    log_success "Ollama service already running"
fi

# Check if model is downloaded
log "Checking if model is available..."
if ! ollama list | grep -q "codellama:${MODEL_SIZE:-13b}-instruct"; then
    log "Downloading model: codellama:${MODEL_SIZE:-13b}-instruct"
    ollama pull codellama:${MODEL_SIZE:-13b}-instruct
fi

log_success "Model ready"

# Start Flask application
log "Starting Flask application..."
log_success "Terraform LLM Assistant starting on http://localhost:${PORT:-5000}"

# Determine which app file to use
APP_FILE="app.py"
if [[ -f "native_app.py" ]]; then
    APP_FILE="native_app.py"
elif [[ ! -f "$APP_FILE" ]]; then
    if [[ -f "simple_flask_app.py" ]]; then
        APP_FILE="simple_flask_app.py"
    elif [[ -f "basic_app.py" ]]; then
        APP_FILE="basic_app.py"
    elif [[ -f "minimal_app.py" ]]; then
        APP_FILE="minimal_app.py"
    fi
fi

python "$APP_FILE"
EOF

    chmod +x "$INSTALL_DIR/start.sh"

    # Create stop script
    cat > "$INSTALL_DIR/stop.sh" << 'EOF'
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

# Stop Ollama service
pkill -f "ollama serve" && log "Ollama service stopped" || log_error "Ollama service not running"

log "Terraform LLM Assistant stopped"
EOF

    chmod +x "$INSTALL_DIR/stop.sh"

    log_success "Startup scripts created"
}

# Check port availability
check_ports() {
    log_header "Checking Port Availability"

    if port_in_use "$WEB_PORT"; then
        log_warning "Web port $WEB_PORT is already in use"
        NEW_PORT=$(find_available_port $((WEB_PORT + 1)) 20)
        if [ "$NEW_PORT" != "$WEB_PORT" ]; then
            WEB_PORT=$NEW_PORT
            log_warning "Using alternative web port: $WEB_PORT"
            # Update .env file
            sed -i "s/PORT=.*/PORT=$WEB_PORT/" "$INSTALL_DIR/.env"
        fi
    fi

    if port_in_use "$OLLAMA_PORT"; then
        log_warning "Ollama port $OLLAMA_PORT is already in use"
        NEW_PORT=$(find_available_port $((OLLAMA_PORT + 1)) 10)
        if [ "$NEW_PORT" != "$OLLAMA_PORT" ]; then
            OLLAMA_PORT=$NEW_PORT
            log_warning "Using alternative Ollama port: $OLLAMA_PORT"
            # Update .env file
            sed -i "s/OLLAMA_PORT=.*/OLLAMA_PORT=$OLLAMA_PORT/" "$INSTALL_DIR/.env"
        fi
    fi

    log_success "Ports checked and configured"
}

# Main deployment function
deploy() {
    log_header "Deploying Terraform LLM Assistant (Native Mode)"

    check_requirements
    install_ollama
    setup_directories
    copy_app_files
    setup_python_env
    create_env_config
    check_ports
    create_startup_script

    log_header "Deployment Complete"

    log_success "Terraform LLM Assistant has been deployed to: $INSTALL_DIR"
    echo ""
    log "To start the application:"
    log "  cd $INSTALL_DIR"
    log "  ./start.sh"
    echo ""
    log "To stop the application:"
    log "  cd $INSTALL_DIR"
    log "  ./stop.sh"
    echo ""
    log "The web interface will be available at: http://localhost:$WEB_PORT"
    log "Logs will be stored in: $INSTALL_DIR/logs/"
}

# Cleanup function
cleanup() {
    log_header "Cleaning up Terraform LLM Assistant"

    if [[ -d "$INSTALL_DIR" ]]; then
        log "Stopping any running services..."
        if [[ -f "$INSTALL_DIR/stop.sh" ]]; then
            cd "$INSTALL_DIR" && ./stop.sh
        fi

        log "Removing installation directory: $INSTALL_DIR"
        rm -rf "$INSTALL_DIR"
        log_success "Cleanup completed"
    else
        log_warning "Installation directory not found: $INSTALL_DIR"
    fi
}

# Show usage
usage() {
    echo "Usage: $0 [COMMAND] [OPTIONS]"
    echo ""
    echo "Commands:"
    echo "  deploy    Deploy the application (default)"
    echo "  clean     Remove the application completely"
    echo "  help      Show this help message"
    echo ""
    echo "Environment Variables:"
    echo "  INSTALL_DIR   Installation directory (default: ~/terraform-llm-assistant)"
    echo "  WEB_PORT      Web server port (default: 5000)"
    echo "  OLLAMA_PORT   Ollama service port (default: 11434)"
    echo "  MODEL_SIZE    Model size: 7b, 13b, 34b (default: 13b)"
    echo "  PYTHON_CMD    Python command (default: python3)"
    echo ""
    echo "Examples:"
    echo "  $0                                    # Deploy with defaults"
    echo "  MODEL_SIZE=7b $0                     # Deploy with 7b model"
    echo "  WEB_PORT=8080 $0                     # Deploy on port 8080"
    echo "  INSTALL_DIR=/opt/terraform-llm $0    # Deploy to /opt/terraform-llm"
    echo "  $0 clean                            # Remove installation"
}

# Command processing
case "${1:-deploy}" in
    deploy)
        deploy
        ;;
    clean)
        cleanup
        ;;
    help|--help|-h)
        usage
        ;;
    *)
        log_error "Unknown command: $1"
        usage
        exit 1
        ;;
esac
