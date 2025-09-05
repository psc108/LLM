#!/usr/bin/env bash
set -euo pipefail

# Restart script for Terraform LLM Assistant
# This script stops any conflicting containers, then starts the assistant

# Container and port settings
ENGINE="${CONTAINER_ENGINE:-docker}"
CONTAINER_NAME="${CONTAINER_NAME:-terraform-llm-assistant}"
WEB_PORT="${PUBLISH_PORT:-8080}"
OLLAMA_PORT="${OLLAMA_PORT:-11434}"
ALT_PORT="5000"

# Colorized output helpers
RED="\033[0;31m"
GREEN="\033[0;32m"
YELLOW="\033[0;33m"
BLUE="\033[0;34m"
NC="\033[0m" # No Color

log() { printf "${BLUE}[%s]${NC} %s\n" "$(date +%H:%M:%S)" "$*"; }
ok() { printf "${GREEN}[%s] ✅ %s${NC}\n" "$(date +%H:%M:%S)" "$*"; }
warn() { printf "${YELLOW}[%s] ⚠️ %s${NC}\n" "$(date +%H:%M:%S)" "$*" >&2; }
error() { printf "${RED}[%s] ❌ %s${NC}\n" "$(date +%H:%M:%S)" "$*" >&2; }

# Check if the container engine is available
if ! command -v "$ENGINE" >/dev/null 2>&1; then
    error "$ENGINE not found. Please install $ENGINE or set CONTAINER_ENGINE environment variable."
    exit 1
fi

# Check if the engine is running
if ! "$ENGINE" info >/dev/null 2>&1; then
    error "$ENGINE is not running or not accessible to this user."
    exit 1
fi

# Function to check if a port is in use
port_in_use() {
    local port=$1

    if command -v ss &>/dev/null; then
        ss -tulpn 2>/dev/null | grep -q ":$port " && return 0
    elif command -v netstat &>/dev/null; then
        netstat -tulpn 2>/dev/null | grep -q ":$port " && return 0
    elif command -v lsof &>/dev/null; then
        lsof -i:"$port" &>/dev/null && return 0
    fi

    return 1
}

# Function to find and stop containers using specific ports
free_ports() {
    local ports=("$@")

    for port in "${ports[@]}"; do
        log "Checking port $port..."

        if port_in_use "$port"; then
            log "Port $port is in use. Trying to find and stop Docker containers using it."

            # Try to find containers using this port
            local container_ids
            container_ids=$($ENGINE ps | grep -E ":$port->|$port:" | awk '{print $1}')

            if [[ -n "$container_ids" ]]; then
                log "Found containers using port $port: $container_ids"
                log "Stopping these containers..."

                for container in $container_ids; do
                    $ENGINE stop "$container" || warn "Could not stop container $container"
                done
            else
                warn "Could not identify Docker containers using port $port."
                warn "The port may be used by another process."
            fi
        else
            ok "Port $port is available."
        fi
    done
}

# Function to stop existing assistant container
stop_assistant() {
    log "Checking for existing $CONTAINER_NAME container..."

    if $ENGINE ps -a -f "name=$CONTAINER_NAME" | grep -q "$CONTAINER_NAME"; then
        log "Stopping existing $CONTAINER_NAME container..."
        $ENGINE stop "$CONTAINER_NAME" &>/dev/null || true
        log "Removing $CONTAINER_NAME container..."
        $ENGINE rm "$CONTAINER_NAME" &>/dev/null || true
        ok "Removed existing container."
    else
        ok "No existing container found."
    fi
}

# Function to start the assistant
start_assistant() {
    log "Starting Terraform LLM Assistant..."

    # Build arguments for the docker run command
    local run_args=(
        -d
        --name "$CONTAINER_NAME"
        -p "$WEB_PORT:8080"
        -p "$OLLAMA_PORT:11434"
        -e PORT="8080"
        -e OLLAMA_PORT="11434"
        -v "$HOME/terraform-llm-assistant:/data:Z"
        --restart unless-stopped
    )

    # Run the container
    if $ENGINE run "${run_args[@]}" "terraform-llm-assistant:local"; then
        ok "Started Terraform LLM Assistant container."
        ok "Web interface available at: http://localhost:$WEB_PORT"
        ok "Ollama API available at: http://localhost:$OLLAMA_PORT"
    else
        error "Failed to start container."
        exit 1
    fi
}

# Main function
main() {
    log "Starting Terraform LLM Assistant restart procedure"

    # First stop any containers using our ports
    log "Checking for port conflicts..."
    free_ports "$WEB_PORT" "$OLLAMA_PORT" "$ALT_PORT"

    # Then stop our container if it's running
    stop_assistant

    # Finally start our container
    start_assistant

    log "Waiting for services to initialize..."
    sleep 5

    # Check container status
    if $ENGINE ps -f "name=$CONTAINER_NAME" | grep -q "$CONTAINER_NAME"; then
        ok "Terraform LLM Assistant is running!"
        log "To access the web interface, open: http://localhost:$WEB_PORT"
        log "To check logs, run: $ENGINE logs -f $CONTAINER_NAME"
    else
        error "Container failed to start or crashed. Check logs:"
        $ENGINE logs "$CONTAINER_NAME"
        exit 1
    fi
}

main "$@"
