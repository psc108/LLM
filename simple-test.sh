#!/bin/bash

CONTAINER_NAME="terraform-llm-assistant"

echo "============================================"
echo "🧪 CREATING SIMPLE TEST APP"
echo "============================================"

# Create a simple test app inside the container
docker exec $CONTAINER_NAME bash -c 'cat > /app/simple_test.py << EOF
from flask import Flask
import os

app = Flask(__name__)

@app.route("/")
def hello():
    return "<h1>Hello from simple test</h1><p>If you see this, Flask is working!</p>"

if __name__ == "__main__":
    port = 7000
    print(f"Starting simple test on port {port}")
    app.run(host="0.0.0.0", port=port)
EOF'

# Check if Flask is installed
echo "\n🔍 Testing if Flask is installed..."
if docker exec $CONTAINER_NAME python3 -c "import flask; print(f'Flask {flask.__version__} is installed')" 2>/dev/null; then
  echo "✅ Flask is installed! Trying to run test app"

  # Run the test app in the background
  docker exec -d $CONTAINER_NAME python3 /app/simple_test.py

  # Wait a bit for it to start
  sleep 2

  # Test connection from inside container
  echo "\n🔍 Testing connection inside container:"
  docker exec $CONTAINER_NAME curl -s http://localhost:7000/ || echo "Cannot connect inside container"

  # Test connection from host
  echo "\n🔍 Testing connection from host (only works with port forwarding):"
  curl -s http://localhost:7000/ || echo "Cannot connect from host (did you publish port 7000?)"
else
  echo "❌ Flask is NOT installed! This is the core issue."  
  echo "\nTo fix this, run:"  
  echo "docker exec $CONTAINER_NAME pip install flask"  
fi
