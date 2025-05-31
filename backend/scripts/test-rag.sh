#!/bin/bash
# Save this as test-rag.sh and run with: bash test-rag.sh

echo "Testing RAG logging in Docker container"

# Run a test query against the RAG module
docker exec backend bash -c "cd /app && python -c 'from rag import query_rag; query_rag(\"What is Mobeus Assistant?\")'"

# Check if log file was created
echo "Checking for log file..."
docker exec backend bash -c "ls -la /app/logs"

# Display log contents if it exists
echo "Log contents (if file exists):"
docker exec backend bash -c "cat /app/logs/rag_debug.jsonl 2>/dev/null || echo 'Log file not found'"

echo "Test complete"