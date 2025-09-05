#!/bin/bash

# Set error handling
set -e

# Color codes for output
RED="\033[0;31m"
GREEN="\033[0;32m"
YELLOW="\033[0;33m"
BLUE="\033[0;36m"
NC="\033[0m" # No Color

# Project name
PROJECT_NAME="terraform-llm"

# Logging functions
log() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
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

# Display warning message
echo -e "${RED}===============================================================${NC}"
echo -e "${RED}= WARNING: This script will forcibly remove ALL resources! =${NC}"
echo -e "${RED}===============================================================${NC}"
echo ""
echo -e "This script will:"  
echo -e " 1. Force stop all ${PROJECT_NAME} containers"
echo -e " 2. Remove all ${PROJECT_NAME} containers"
echo -e " 3. Remove all ${PROJECT_NAME} volumes (permanent data loss)"
echo -e " 4. Remove all ${PROJECT_NAME} networks"
echo ""

# Find all project-related containers
log "Scanning for ${PROJECT_NAME} containers..."
CONTAINERS=$($DOCKER_CMD ps -a --format '{{.Names}}' | grep -E "${PROJECT_NAME}" || true)

# Report findings
if [ -n "$CONTAINERS" ]; then
    log "Found the following containers:"
    echo "$CONTAINERS" | while read -r container; do
        echo "  - $container"
    done
else
    log "No ${PROJECT_NAME} containers found"
fi

# Find related volumes
log "Scanning for ${PROJECT_NAME} volumes..."
VOLUMES=$($DOCKER_CMD volume ls --format '{{.Name}}' | grep -E "${PROJECT_NAME}" || true)

# Report findings
if [ -n "$VOLUMES" ]; then
    log "Found the following volumes:"
    echo "$VOLUMES" | while read -r volume; do
        echo "  - $volume"
    done
else
    log "No ${PROJECT_NAME} volumes found"
fi

# Ask for confirmation
read -p "Continue with cleanup? This CANNOT be undone. (yes/no): " CONFIRM
if [ "$CONFIRM" != "yes" ]; then
    log "Operation cancelled"
    exit 0
fi

# Stop all containers
if [ -n "$CONTAINERS" ]; then
    log "Stopping containers..."
    echo "$CONTAINERS" | while read -r container; do
        $DOCKER_CMD stop "$container" 2>/dev/null || true
        log "Stopped: $container"
    done
fi

# Remove all containers
if [ -n "$CONTAINERS" ]; then
    log "Removing containers..."
    echo "$CONTAINERS" | while read -r container; do
        $DOCKER_CMD rm -f "$container" 2>/dev/null || true
        log "Removed: $container"
    done
fi

# Remove all volumes
if [ -n "$VOLUMES" ]; then
    log "Removing volumes..."
    echo "$VOLUMES" | while read -r volume; do
        $DOCKER_CMD volume rm -f "$volume" 2>/dev/null || true
        log "Removed: $volume"
    done
fi

# Find related networks
log "Scanning for ${PROJECT_NAME} networks..."
NETWORKS=$($DOCKER_CMD network ls --format '{{.Name}}' | grep -E "${PROJECT_NAME}" || true)

# Remove related networks
if [ -n "$NETWORKS" ]; then
    log "Removing networks..."
    echo "$NETWORKS" | while read -r network; do
        $DOCKER_CMD network rm "$network" 2>/dev/null || true
        log "Removed: $network"
    done
fi

# Final success message
log_success "Cleanup completed successfully. All ${PROJECT_NAME} resources have been removed."
log "You can now start with a fresh installation."
