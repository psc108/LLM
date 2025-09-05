#!/bin/bash

# Set strict error handling
set -e

# Color codes for output
RED="\033[0;31m"
GREEN="\033[0;32m"
YELLOW="\033[0;33m"
BLUE="\033[0;34m"
CYAN="\033[0;36m"
NC="\033[0m" # No Color

# Project name - used for container and volume naming
PROJECT_NAME="terraform-llm"

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

log_header() {
    echo -e "${CYAN}=======================================================${NC}"
    echo -e "${CYAN}== $1${NC}"
    echo -e "${CYAN}=======================================================${NC}"
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

# Find containers by pattern
find_containers() {
    local pattern="$1"
    local containers=$($DOCKER_CMD ps -a --format '{{.Names}}' | grep -E "${pattern}" || true)
    echo "$containers"
}

# List all containers with details
list_containers() {
    log_header "Container Management"

    # Find containers by pattern (default to project name)
    local pattern="${1:-$PROJECT_NAME}"
    local containers=$(find_containers "$pattern")

    if [ -z "$containers" ]; then
        log "No containers matching '$pattern' found."
        return 0
    fi

    log "Found containers matching '$pattern':"
    echo ""
    # Show detailed table
    $DOCKER_CMD ps -a --format "table {{.Names}}\t{{.Status}}\t{{.Image}}\t{{.Ports}}" | \
        (echo -e "${YELLOW}NAME\tSTATUS\tIMAGE\tPORTS${NC}" && grep -E "$pattern")
    echo ""
}

# Multi-select menu for container operations
container_menu() {
    local pattern="${1:-$PROJECT_NAME}"
    local containers=$(find_containers "$pattern")

    if [ -z "$containers" ]; then
        log_warning "No containers found matching '$pattern'"
        return 0
    fi

    # List containers with numbers
    log "Select containers to manage:"
    local container_array=()
    local i=1
    while IFS= read -r container; do
        container_array+=($container)
        # Get status (running/exited)
        local status=$($DOCKER_CMD ps -a --format '{{.Status}}' --filter "name=$container" | grep -o "^[^ ]*")
        if [[ "$status" == "Up" ]]; then
            echo -e "  ${GREEN}$i)${NC} $container ${GREEN}[Running]${NC}"
        else
            echo -e "  ${YELLOW}$i)${NC} $container ${YELLOW}[$status]${NC}"
        fi
        i=$((i+1))
    done <<< "$containers"

    # Add options for all containers
    echo -e "  ${BLUE}a)${NC} All containers"
    echo -e "  ${BLUE}r)${NC} All running containers"
    echo -e "  ${BLUE}s)${NC} All stopped containers"
    echo -e "  ${BLUE}q)${NC} Cancel/Back"

    # Get selection
    local valid_selection=false
    local selection_array=()

    while [ "$valid_selection" = false ]; do
        read -p "Enter your choice (number, a, r, s, or q): " choice

        case "$choice" in
            [1-9]|[1-9][0-9])
                if [ "$choice" -le "${#container_array[@]}" ]; then
                    selection_array+=("${container_array[$choice-1]}")
                    valid_selection=true
                else
                    log_error "Invalid selection. Please try again."
                fi
                ;;
            "a")
                selection_array=(${container_array[@]})
                valid_selection=true
                ;;
            "r")
                # Get only running containers
                local running=$($DOCKER_CMD ps --format '{{.Names}}' | grep -E "$pattern" || true)
                selection_array=()
                while IFS= read -r container; do
                    selection_array+=("$container")
                done <<< "$running"

                if [ ${#selection_array[@]} -eq 0 ]; then
                    log_warning "No running containers found."
                    return 0
                fi
                valid_selection=true
                ;;
            "s")
                # Get only stopped containers
                local all_containers=(${container_array[@]})
                local running=$($DOCKER_CMD ps --format '{{.Names}}' | grep -E "$pattern" || true)
                selection_array=()

                for container in "${all_containers[@]}"; do
                    if ! echo "$running" | grep -q "$container"; then
                        selection_array+=("$container")
                    fi
                done

                if [ ${#selection_array[@]} -eq 0 ]; then
                    log_warning "No stopped containers found."
                    return 0
                fi
                valid_selection=true
                ;;
            "q")
                log "Operation cancelled"
                return 0
                ;;
            *)
                log_error "Invalid choice. Please try again."
                ;;
        esac
    done

    # Show selected containers
    log "Selected containers:"
    for container in "${selection_array[@]}"; do
        echo "  - $container"
    done

    # Action menu
    echo -e "\n${YELLOW}Select action:${NC}"
    echo "  1) Stop containers"
    echo "  2) Start containers"
    echo "  3) Restart containers"
    echo "  4) Remove containers"
    echo "  5) View logs"
    echo "  6) Show container details"
    echo "  7) Cancel"

    read -p "Enter action (1-7): " action_choice

    case "$action_choice" in
        1) # Stop containers
            for container in "${selection_array[@]}"; do
                if $DOCKER_CMD ps --format '{{.Names}}' | grep -q "^$container$"; then
                    log "Stopping container: $container"
                    $DOCKER_CMD stop "$container" || log_warning "Failed to stop $container"
                else
                    log_warning "$container is not running"
                fi
            done
            log_success "Container operation completed"
            ;;
        2) # Start containers
            for container in "${selection_array[@]}"; do
                if ! $DOCKER_CMD ps --format '{{.Names}}' | grep -q "^$container$"; then
                    log "Starting container: $container"
                    $DOCKER_CMD start "$container" || log_warning "Failed to start $container"
                else
                    log_warning "$container is already running"
                fi
            done
            log_success "Container operation completed"
            ;;
        3) # Restart containers
            for container in "${selection_array[@]}"; do
                log "Restarting container: $container"
                $DOCKER_CMD restart "$container" || log_warning "Failed to restart $container"
            done
            log_success "Container operation completed"
            ;;
        4) # Remove containers
            read -p "Remove containers permanently? This will delete all container data. (y/n): " confirm_remove
            if [ "$confirm_remove" = "y" ] || [ "$confirm_remove" = "Y" ]; then
                for container in "${selection_array[@]}"; do
                    log "Removing container: $container"
                    $DOCKER_CMD rm -f "$container" || log_warning "Failed to remove $container"
                done
                log_success "Container operation completed"
            else
                log "Remove operation cancelled"
            fi
            ;;
        5) # View logs
            if [ ${#selection_array[@]} -eq 1 ]; then
                log "Showing logs for ${selection_array[0]}"
                echo -e "${YELLOW}Press Ctrl+C to exit logs${NC}"
                sleep 1
                $DOCKER_CMD logs -f "${selection_array[0]}"
            else
                log_error "Please select only one container for viewing logs"
            fi
            ;;
        6) # Show container details
            for container in "${selection_array[@]}"; do
                log_header "Details for $container"
                $DOCKER_CMD inspect "$container" | grep -E 'Name|Image|Status|Path|Args|Port|Mount|Network|IPAddress|HealthCheck'
            done
            log_success "Container operation completed"
            ;;
        7|*) # Cancel or invalid
            log "Operation cancelled"
            ;;
    esac
}

# Main function
main() {
    # Parse command line arguments
    local command="$1"
    local pattern="$2"

    case "$command" in
        list)
            list_containers "${pattern:-$PROJECT_NAME}"
            ;;
        manage)
            list_containers "${pattern:-$PROJECT_NAME}"
            container_menu "${pattern:-$PROJECT_NAME}"
            ;;
        clean)
            log_header "Cleaning Containers"
            list_containers "${pattern:-$PROJECT_NAME}"

            read -p "Are you sure you want to remove ALL these containers? (y/n): " confirm
            if [ "$confirm" = "y" ] || [ "$confirm" = "Y" ]; then
                local containers=$(find_containers "${pattern:-$PROJECT_NAME}")
                if [ -n "$containers" ]; then
                    while IFS= read -r container; do
                        log "Removing container: $container"
                        $DOCKER_CMD rm -f "$container" || log_warning "Failed to remove $container"
                    done <<< "$containers"
                    log_success "All containers removed"
                else
                    log "No containers to remove"
                fi
            else
                log "Operation cancelled"
            fi
            ;;
        *)
            log_header "Container Manager Help"
            echo "Usage: $0 COMMAND [PATTERN]"
            echo ""
            echo "Commands:"
            echo "  list [pattern]    List containers matching the pattern"
            echo "  manage [pattern]  Manage containers (stop, start, remove, etc.)"
            echo "  clean [pattern]   Remove all containers matching the pattern"
            echo ""
            echo "Examples:"
            echo "  $0 list            List all terraform-llm containers"
            echo "  $0 list mysql      List all containers with 'mysql' in the name"
            echo "  $0 manage         Show interactive management menu"
            echo "  $0 clean          Remove all terraform-llm containers"
            echo ""
            ;;
    esac
}

# Run main with arguments
main "$@"
