#!/bin/bash
set -e

echo "🔍 Testing container connectivity"
echo "=============================================="

# Defaults
CONTAINER_NAME="${CONTAINER_NAME:-terraform-llm-assistant}"
WEB_PORT="${PUBLISH_PORT:-8080}"

# Function to check if a container exists and is running
check_container() {
    if ! docker ps -q -f name=$CONTAINER_NAME | grep -q .; then
        echo "❌ Container '$CONTAINER_NAME' is not running!"

        # Check if it exists but is stopped
        if docker ps -a -q -f name=$CONTAINER_NAME | grep -q .; then
            echo "ℹ️  Container exists but is stopped. Checking logs:"
            docker logs --tail 20 $CONTAINER_NAME
            echo ""
            echo "To start the container: docker start $CONTAINER_NAME"
        else
            echo "ℹ️  Container does not exist. Run deploy.sh to create it."
        fi

        exit 1
    fi

    echo "✅ Container '$CONTAINER_NAME' is running"
}

# Function to check port connectivity
check_port() {
    local port=$1
    local description=$2

    echo "🔍 Testing connectivity to $description on port $port"

    # Try netcat if available
    if command -v nc > /dev/null; then
        if nc -z localhost $port; then
            echo "✅ Port $port is open and accessible"
        else
            echo "❌ Port $port is not accessible"
            return 1
        fi
    # Try curl as alternative
    elif command -v curl > /dev/null; then
        if curl -s -m 2 http://localhost:$port > /dev/null; then
            echo "✅ HTTP service responding on port $port"
        else
            echo "❌ HTTP request to port $port failed"
            return 1
        fi
    else
        echo "⚠️  No tools available to check port connectivity"
        return 1
    fi

    return 0
}

# Function to test HTTP endpoints
test_http() {
    local port=$1
    local endpoints=("" "/health" "/api/debug")

    for endpoint in "${endpoints[@]}"; do
        echo "🌐 Testing HTTP endpoint: http://localhost:$port$endpoint"
        if curl -s -m 5 -D - "http://localhost:$port$endpoint" | head -n 20; then
            echo "✅ Endpoint http://localhost:$port$endpoint is accessible"
        else
            echo "❌ Endpoint http://localhost:$port$endpoint failed"
        fi
        echo ""
    done
}

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running or not accessible!"
    exit 1
fi

# Check container status
check_container

# Get published ports for the container
echo "🔍 Checking published ports for $CONTAINER_NAME"
docker port $CONTAINER_NAME

# Test web port
check_port $WEB_PORT "web server"

# Test Ollama port
check_port 11434 "Ollama API"

# Test HTTP endpoints
echo "🌐 Testing HTTP endpoints"
test_http $WEB_PORT

# Show container logs
echo "📋 Container logs (last 20 lines):"
docker logs --tail 20 $CONTAINER_NAME

echo ""
echo "✅ Test completed"
