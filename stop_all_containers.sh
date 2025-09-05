#!/usr/bin/env bash
set -euo pipefail

# Utility script to stop and remove all Docker containers

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

# Function to stop all containers
stop_all_containers() {
    log "Getting list of running containers..."

    # Get all running container IDs
    local containers
    containers=$($ENGINE ps -q)

    # Check if there are any running containers
    if [[ -z "$containers" ]]; then
        ok "No running containers found."
        return 0
    fi

    # Count running containers
    local count
    count=$($ENGINE ps | wc -l)
    count=$((count - 1)) # Subtract header line

    log "Found $count running container(s)."

    # Ask for confirmation
    read -p "${YELLOW}Are you sure you want to stop and remove all running containers? [y/N]:${NC} " -r confirm
    echo # New line

    if [[ ! $confirm =~ ^[Yy]$ ]]; then
        warn "Operation cancelled."
        exit 0
    fi

    # Stop all containers
    log "Stopping all containers..."
    $ENGINE stop $containers

    # Remove all containers (including non-running ones)
    log "Removing all containers..."

    # Only if the user wants to remove all containers
    read -p "${YELLOW}Do you also want to remove all stopped containers? [y/N]:${NC} " -r remove_confirm
    echo # New line

    if [[ $remove_confirm =~ ^[Yy]$ ]]; then
        $ENGINE rm $($ENGINE ps -a -q) 2>/dev/null || true
        ok "All containers have been removed."
    else
        ok "All containers have been stopped."
    fi
}

# Function to show status
show_status() {
    log "Current containers status:"
    $ENGINE ps -a
}

# Main
main() {
    log "Starting container cleanup process using $ENGINE"

    # Show initial status
    show_status

    # Stop and remove all containers
    stop_all_containers

    # Show final status
    log "Final status:"
    show_status

    ok "Container cleanup completed."
}

main "$@"
