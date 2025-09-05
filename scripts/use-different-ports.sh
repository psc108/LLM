#!/bin/bash

# Default values
FLASK_PORT=9000
OLLAMA_PORT=12434

# Help text
if [[ "$1" == "-h" || "$1" == "--help" ]]; then
  echo "Usage: $0 [flask_port] [ollama_port]"
  echo "  flask_port: Web interface port (default: 9000)"
  echo "  ollama_port: Ollama API port (default: 12434)"
  echo ""
  echo "Example: $0 9000 12434"
  exit 0
fi

# Get custom ports from arguments
if [[ -n "$1" ]]; then
  FLASK_PORT=$1
fi

if [[ -n "$2" ]]; then
  OLLAMA_PORT=$2
fi

echo "Starting with Web UI on port $FLASK_PORT and Ollama API on port $OLLAMA_PORT"

# Run deploy.sh with custom ports
PUBLISH_PORT=$FLASK_PORT OLLAMA_PORT=$OLLAMA_PORT CONTAINER_PORT=8080 ./deploy.sh

echo "------------------------------------------------------"
echo "Access the web interface at: http://localhost:$FLASK_PORT"
echo "Access the Ollama API at: http://localhost:$OLLAMA_PORT"
echo "------------------------------------------------------"
