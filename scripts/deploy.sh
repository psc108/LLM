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

# Function to check for existing containers
check_existing_containers() {
    log "Checking for existing ${PROJECT_NAME} containers..."

    # Get all containers (running and stopped) that match our project name
    local containers=$($DOCKER_CMD ps -a --format '{{.Names}}' | grep -E "${PROJECT_NAME}" || true)

    if [ -z "$containers" ]; then
        log "No existing ${PROJECT_NAME} containers found."
        return 0
    fi

    # Display found containers
    log_warning "Found existing containers:"

    # Show containers with details
    $DOCKER_CMD ps -a --format "table {{.Names}}\t{{.Status}}\t{{.Image}}\t{{.Ports}}" | grep -E "${PROJECT_NAME}"

    # Ask user what to do
    echo -e "\n${YELLOW}Existing containers may conflict with this deployment.${NC}"
    read -p "Would you like to remove these containers? (y/n): " choice

    if [ "$choice" = "y" ] || [ "$choice" = "Y" ]; then
        log "Removing containers..."

        for container in $containers; do
            log "Removing container: $container"
            $DOCKER_CMD rm -f "$container" || log_warning "Failed to remove $container"
        done

        log_success "Containers removed successfully"
    else
        log "Keeping existing containers"
        echo ""
        log_warning "Note: You may encounter port conflicts if you continue."
        read -p "Continue with deployment anyway? (y/n): " continue_choice

        if [ "$continue_choice" != "y" ] && [ "$continue_choice" != "Y" ]; then
            log "Deployment aborted by user"
            exit 0
        fi
    fi
}

# Main deploy function
deploy() {
    log "Starting deployment of ${PROJECT_NAME}..."

    # Check for existing containers and handle them
    check_existing_containers

    # Pull the latest image
    log "Pulling the latest image from $REGISTRY_URL/${PROJECT_NAME}:latest"
    $DOCKER_CMD pull "$REGISTRY_URL/${PROJECT_NAME}:latest"

    # Run the container
    log "Starting container..."
    $DOCKER_CMD run -d \
      -p 5000:5000 \
      -p 11434:11434 \
      --name "${PROJECT_NAME}" \
      "$REGISTRY_URL/${PROJECT_NAME}:latest"

    log_success "${PROJECT_NAME} has been deployed successfully"
    log "Web interface will be available at: http://localhost:5000"
    log "Note: The system may take 1-3 minutes to fully initialize"
    log "To view startup progress, run: $DOCKER_CMD logs -f ${PROJECT_NAME}"
}

# Command processing
case "$1" in
    deploy)
        deploy
        ;;
    clean)
        # Clean up all resources
        log "Cleaning up all ${PROJECT_NAME} resources..."
        $DOCKER_CMD rm -f "${PROJECT_NAME}" 2>/dev/null || true
        $DOCKER_CMD volume rm -f "${PROJECT_NAME}_data" 2>/dev/null || true
        log_success "Cleanup completed successfully"
        ;;
    *)
        log "Usage: $0 {deploy|clean}"
        log "  deploy - Deploy the ${PROJECT_NAME} container"
        log "  clean  - Remove container and all associated volumes"
        exit 1
        ;;
esac

log_success "Command completed successfully"
