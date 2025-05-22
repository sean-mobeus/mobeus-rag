#!/bin/bash
# Save this as debug-docker-logs.sh and run with: bash debug-docker-logs.sh

# Create the logs directory if it doesn't exist
mkdir -p logs
chmod 777 logs  # Ensure all users (including Docker container user) can write to this directory

echo "Created logs directory with write permissions"

# Check if backend container is running
if ! docker ps | grep -q "backend"; then
  echo "Backend container is not running. Starting containers..."
  docker-compose up -d
  sleep 5  # Give containers time to start
fi

# Check Docker logs for any errors
echo "Checking Docker logs for errors..."
docker-compose logs --tail=100 backend | grep -i "error\|warning\|fail"

# Execute debug command inside the container
echo "Running debug commands inside container..."
docker exec backend bash -c "ls -la /app/logs"
docker exec backend bash -c "python -c 'import os; print(\"Log dirs:\", os.path.exists(\"/app/logs\"))'"
docker exec backend bash -c "python -c 'import os; print(\"App dir contents:\", os.listdir(\"/app\"))'"

# Check python config
echo "Testing DEBUG_LOG_PATH in container..."
docker exec backend bash -c "python -c 'from config import DEBUG_LOG_PATH; print(\"Log path:\", DEBUG_LOG_PATH)'"

# Try to write a test log entry
echo "Trying to write a test log entry..."
docker exec backend bash -c "python -c 'import json, datetime; open(\"/app/logs/test.log\", \"a\").write(json.dumps({\"test\": True, \"timestamp\": datetime.datetime.now().isoformat()}) + \"\\n\")'"

# Check if test file was created
echo "Checking if test log was created..."
docker exec backend bash -c "ls -la /app/logs"

echo "Done debugging"