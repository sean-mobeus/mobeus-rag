#!/bin/bash
# This script helps verify Docker setup and check build issues

echo "===== Docker Diagnostic Script ====="

# Check if Docker is running
echo "1. Checking if Docker is running..."
if ! docker info > /dev/null 2>&1; then
  echo "❌ Docker is not running! Please start Docker Desktop or the Docker service."
  exit 1
else
  echo "✅ Docker is running"
fi

# List running containers
echo -e "\n2. Listing running containers..."
docker ps

# Check container logs (replace with your container names)
echo -e "\n3. Checking frontend container logs (last 10 lines)..."
docker logs --tail 10 frontend-1 2>&1 || echo "No container named frontend-1"

echo -e "\n4. Checking backend container logs (last 10 lines)..."
docker logs --tail 10 backend 2>&1 || echo "No container named backend"

# Check if containers are healthy
echo -e "\n5. Checking container health..."
docker ps --format "{{.Names}}: {{.Status}}"

# Check network
echo -e "\n6. Checking Docker networks..."
docker network ls

# Try to curl the backend from inside the frontend container
echo -e "\n7. Testing connectivity from frontend to backend..."
docker exec frontend-1 curl -s -o /dev/null -w "%{http_code}" http://backend:8010/ || echo "Failed to execute curl inside frontend container"

# Check volume mounts
echo -e "\n8. Checking volume mounts..."
docker inspect frontend-1 -f '{{ range .Mounts }}{{ .Source }} -> {{ .Destination }}{{ println }}{{ end }}' || echo "Failed to inspect frontend volumes"

echo -e "\n===== Diagnostic Complete ====="
echo "If you're still having issues, try:"
echo "1. docker-compose down"
echo "2. docker-compose build --no-cache"
echo "3. docker-compose up"