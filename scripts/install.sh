#!/bin/bash

# Set strict error handling
set -e

# Color codes for output
RED="\033[0;31m"
GREEN="\033[0;32m"
YELLOW="\033[0;33m"
BLUE="\033[0;34m"
NC="\033[0m" # No Color

# Project name - used for container and volume naming
PROJECT_NAME="terraform-llm"
REGISTRY_URL="registry.example.com"
MODEL_NAME="codellama:13b-terraform"
USE_PERSISTENT_STORAGE=true

# Logging functions
log() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check for docker or podman
DOCKER_CMD="docker"
if ! command -v docker &> /dev/null; then
    if command -v podman &> /dev/null; then
        log "Docker not found, using Podman instead"
        DOCKER_CMD="podman"
    else
        log_error "Neither Docker nor Podman found. Please install one of them first."
        exit 1
    fi
fi

# Function to manage existing containers
manage_existing_containers() {
    log "Checking for existing containers..."

    # Get containers related to our project
    local all_containers=$($DOCKER_CMD ps -a --format '{{.Names}}' | grep -E "${PROJECT_NAME}" || true)
    local running_containers=$($DOCKER_CMD ps --format '{{.Names}}' | grep -E "${PROJECT_NAME}" || true)

    if [ -z "$all_containers" ]; then
        log "No existing containers found. Proceeding with installation."
        return 0
    fi

    log_warning "Found existing containers:"

    # Display in a nice table format
    echo -e "\n${YELLOW}EXISTING CONTAINERS:${NC}"
    $DOCKER_CMD ps -a --format "table {{.Names}}\t{{.Status}}\t{{.Image}}\t{{.Ports}}" | grep -E "${PROJECT_NAME}"

    # Prompt user for action
    echo -e "\n${YELLOW}Select an action:${NC}"
    echo "1) Remove all containers and continue with fresh installation"
    echo "2) Stop running containers but keep data"
    echo "3) Keep containers and abort installation"
    echo "4) Force continue (may cause conflicts)"

    local valid_input=false
    while [ "$valid_input" = false ]; do
        read -p "Enter your choice (1-4): " container_action

        case "$container_action" in
            1)
                log "Removing all existing containers..."
                for container in $all_containers; do
                    log "Removing container: $container"
                    $DOCKER_CMD rm -f "$container" || log_warning "Failed to remove $container"
                done
                log_success "All containers removed"
                valid_input=true
                ;;
            2)
                if [ -n "$running_containers" ]; then
                    log "Stopping running containers..."
                    for container in $running_containers; do
                        log "Stopping container: $container"
                        $DOCKER_CMD stop "$container" || log_warning "Failed to stop $container"
                    done
                    log_success "Containers stopped"
                else
                    log "No running containers found"
                fi
                valid_input=true
                ;;
            3)
                log "Installation aborted by user"
                exit 0
                ;;
            4)
                log_warning "Continuing with installation despite existing containers"
                log_warning "This may cause port conflicts or other issues"
                valid_input=true
                ;;
            *)
                log_error "Invalid choice. Please enter a number between 1 and 4."
                ;;
        esac
    done
}

# Main install function
install() {
    log "Starting installation of ${PROJECT_NAME}..."

    # Check for system requirements
    log "Checking system requirements..."
    local mem_kb=$(grep MemTotal /proc/meminfo | awk '{print $2}')
    local mem_gb=$((mem_kb / 1024 / 1024))

    if [ $mem_gb -lt 12 ]; then
        log_warning "Your system has only ${mem_gb}GB RAM. At least 16GB is recommended."
        log_warning "You may experience performance issues with the default model."
        echo ""
        echo "Available models based on your system memory:"
        echo "1) Small model (8B parameters) - Recommended for your system"
        echo "2) Medium model (13B parameters) - May be unstable on your system"
        read -p "Choose a model size (1/2): " model_choice

        if [ "$model_choice" = "1" ]; then
            MODEL_NAME="llama3:8b"
            log "Selected small model: $MODEL_NAME"
        else
            log_warning "Continuing with default model, but this may cause system instability"
        fi
    fi

    # Check for existing containers and manage them
    manage_existing_containers

    # Pull the latest image
    log "Pulling the latest image..."
    $DOCKER_CMD pull "$REGISTRY_URL/${PROJECT_NAME}:latest"

    # Run the container with appropriate options
    log "Starting container..."
    if [ "$USE_PERSISTENT_STORAGE" = true ]; then
        log "Using persistent storage for models"
        $DOCKER_CMD run -d \
          -p 5000:5000 \
          -p 11434:11434 \
          -e MODEL_NAME="$MODEL_NAME" \
          -v "${PROJECT_NAME}_models:/opt/app-root/src/.ollama/models" \
          --name "${PROJECT_NAME}" \
          "$REGISTRY_URL/${PROJECT_NAME}:latest"
    else
        $DOCKER_CMD run -d \
          -p 5000:5000 \
          -p 11434:11434 \
          -e MODEL_NAME="$MODEL_NAME" \
          --name "${PROJECT_NAME}" \
          "$REGISTRY_URL/${PROJECT_NAME}:latest"
    fi

    # Report success
    log_success "${PROJECT_NAME} has been installed successfully"
    log "Web interface will be available at: http://localhost:5000"
    log "Note: The system may take 15-30 minutes to fully initialize on first run"
    log "To view startup progress, run: $DOCKER_CMD logs -f ${PROJECT_NAME}"

    # Offer to show logs
    read -p "Would you like to watch the initialization logs now? (y/n): " show_logs
    if [ "$show_logs" = "y" ] || [ "$show_logs" = "Y" ]; then
        $DOCKER_CMD logs -f "${PROJECT_NAME}"
    fi
}

# Command processing
case "$1" in
    install)
        install
        ;;
    uninstall)
        log "Uninstalling ${PROJECT_NAME}..."
        $DOCKER_CMD rm -f "${PROJECT_NAME}" 2>/dev/null || true
        read -p "Remove persistent data as well? (y/n): " remove_data
        if [ "$remove_data" = "y" ] || [ "$remove_data" = "Y" ]; then
            $DOCKER_CMD volume rm -f "${PROJECT_NAME}_models" 2>/dev/null || true
            log_success "${PROJECT_NAME} uninstalled with all data removed"
        else
            log_success "${PROJECT_NAME} uninstalled, persistent data kept"
        fi
        ;;
    list-containers)
        log "Listing all ${PROJECT_NAME} containers:"
        $DOCKER_CMD ps -a --format "table {{.Names}}\t{{.Status}}\t{{.Image}}\t{{.Ports}}" | grep -E "${PROJECT_NAME}" || echo "No containers found"
        ;;
    *)
        log "Usage: $0 {install|uninstall|list-containers}"
        log "  install         - Install ${PROJECT_NAME}"
        log "  uninstall       - Remove the ${PROJECT_NAME} container"
        log "  list-containers - List all ${PROJECT_NAME} containers"
        exit 1
        ;;
esac

log_success "Command completed successfully"
