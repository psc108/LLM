#!/usr/bin/env bash
set -euo pipefail

# Utility script to identify and stop Docker containers using specific ports

# Default ports to check
PORTS_TO_CHECK=(5000 8080 11434)

# Set the container engine (docker or podman)
ENGINE="${CONTAINER_ENGINE:-docker}"

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

# Function to find containers using specific ports
find_containers_by_port() {
    local port=$1
    local container_ids

    log "Looking for containers using port $port..."

    # Use different commands based on available tools
    if command -v docker &>/dev/null; then
        # Using docker directly with inspect to find port mappings
        container_ids=$($ENGINE ps -q | xargs -r $ENGINE inspect --format='{{.Name}} {{range $p, $conf := .NetworkSettings.Ports}}{{range $conf}}{{if eq .HostPort "'"$port"'"}}{{$.Id}}{{end}}{{end}}{{end}}' | grep -v '^$' | awk '{print $1}' | sed 's/^\///')
    elif command -v jq &>/dev/null; then
        # Alternative using jq if available
        container_ids=$($ENGINE ps -q | xargs -r $ENGINE inspect | jq -r '.[] | select(.NetworkSettings.Ports | to_entries | .[].value | if type=="array" then any(.HostPort == "'"$port"'") else false end) | .Name' | sed 's/^\///')
    else
        # Fallback to grepping docker ps output for the port
        container_ids=$($ENGINE ps | grep -E ":$port->" | awk '{print $1}')
    fi

    # Return the container IDs (might be empty)
    echo "$container_ids"
}

# Function to stop containers by port
stop_containers_by_port() {
    local port=$1
    local containers

    # Get containers using this port
    containers=$(find_containers_by_port "$port")

    if [[ -z "$containers" ]]; then
        log "No containers found using port $port."
        return 0
    fi

    log "Found containers using port $port: $containers"

    # Ask for confirmation before stopping
    read -p "${YELLOW}Stop these containers? [y/N]:${NC} " -r confirm
    echo # New line

    if [[ ! $confirm =~ ^[Yy]$ ]]; then
        warn "Skipping port $port."
        return 0
    fi

    # Stop the containers
    for container in $containers; do
        log "Stopping container $container..."
        $ENGINE stop "$container"
        ok "Container $container stopped."
    done
}

# Function to check if a port is in use (by any process, not just Docker)
port_in_use() {
    local port=$1
    local in_use=false

    log "Checking if port $port is in use by any process..."

    # Try different commands to check for port usage
    if command -v ss &>/dev/null; then
        if ss -tulpn | grep -q ":$port "; then
            in_use=true
            log "Port $port is in use according to ss command."
        fi
    elif command -v netstat &>/dev/null; then
        if netstat -tulpn 2>/dev/null | grep -q ":$port "; then
            in_use=true
            log "Port $port is in use according to netstat command."
        fi
    elif command -v lsof &>/dev/null; then
        if lsof -i:"$port" &>/dev/null; then
            in_use=true
            log "Port $port is in use according to lsof command."
        fi
    fi

    if $in_use; then
        return 0 # success = port is in use
    else
        log "Port $port appears to be free."
        return 1 # failure = port is not in use
    fi
}

# Main function
main() {
    # Check if specific ports were passed as arguments
    if [[ $# -gt 0 ]]; then
        PORTS_TO_CHECK=("$@")
    fi

    log "Starting port check and container management using $ENGINE"
    log "Will check the following ports: ${PORTS_TO_CHECK[*]}"

    # Process each port
    for port in "${PORTS_TO_CHECK[@]}"; do
        log "Processing port $port"

        # First check if the port is in use at all
        if port_in_use "$port"; then
            # Try to find Docker containers using this port
            stop_containers_by_port "$port"

            # Check again if the port is still in use after stopping containers
            if port_in_use "$port"; then
                warn "Port $port is still in use by a non-Docker process."
            else
                ok "Port $port is now free."
            fi
        else
            ok "Port $port is already free."
        fi
    done

    log "Port check and container management completed."
}

main "$@"
