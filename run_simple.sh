#!/bin/bash
set -e
#!/bin/bash
set -e

echo "Building a simple Docker image..."
docker build -f Dockerfile.simple -t simple-flask-test .

echo "Running the Docker container with port 5000 exposed..."
docker rm -f simple-flask-test 2>/dev/null || true
docker run -d --name simple-flask-test -p 5000:5000 simple-flask-test

echo "Container started. Wait a moment for Flask to initialize..."
sleep 5

echo "Checking if the Flask app is accessible from host machine..."
if curl -s http://localhost:5000/health; then
  echo -e "\n✅ Success! Flask app is running and accessible at http://localhost:5000"
else
  echo -e "\n❌ Failed to access the Flask app from host. Checking container logs:"
  docker logs simple-flask-test

  echo -e "\n🔍 Checking if Flask is accessible within the container:"
  docker exec simple-flask-test curl -s http://localhost:5000/health || echo "Not accessible inside container either"

  echo -e "\n🔍 Checking network settings:"
  docker inspect simple-flask-test | grep -A 10 "NetworkSettings"
fi

echo -e "\nTo view logs: docker logs simple-flask-test"
echo "To stop container: docker stop simple-flask-test"
echo "Building a simple Docker image..."
docker build -f Dockerfile.simple -t simple-flask-test .

echo "Running the Docker container with port 5000 exposed..."
docker rm -f simple-flask-test 2>/dev/null || true
docker run -d --name simple-flask-test -p 5000:5000 simple-flask-test

echo "Container started. Wait a moment for Flask to initialize..."
sleep 5

echo "Checking if the Flask app is accessible from host machine..."
if curl -s http://localhost:5000/health; then
  echo "\n✅ Success! Flask app is running and accessible at http://localhost:5000"
else
  echo "\n❌ Failed to access the Flask app from host. Checking container logs:"
  docker logs simple-flask-test

  echo "\n🔍 Checking if Flask is accessible within the container:"
  docker exec simple-flask-test curl -s http://localhost:5000/health || echo "Not accessible inside container either"

  echo "\n🔍 Checking network settings:"
  docker inspect simple-flask-test | grep -A 10 "NetworkSettings"
fi

echo "\nTo view logs: docker logs simple-flask-test"
echo "To stop container: docker stop simple-flask-test"
