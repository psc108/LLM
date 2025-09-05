#!/bin/bash
set -e

echo "Building the Docker image..."
docker build -t terraform-llm-assistant .

echo "Running the Docker container..."
docker run -d --name terraform-llm-assistant -p 5000:5000 -p 11434:11434 terraform-llm-assistant

echo "Container started. Wait a moment for Flask to initialize..."
sleep 5

echo "Checking if the Flask app is accessible..."
if curl -s http://localhost:5000/health > /dev/null; then
  echo "✅ Success! Flask app is running and accessible at http://localhost:5000"
else
  echo "❌ Failed to access the Flask app. Checking container logs:"
  docker logs terraform-llm-assistant
fi
