# Mobeus Assistant Admin Dashboard

A comprehensive admin dashboard for monitoring, debugging, and configuring the Mobeus Assistant platform.

## Features

- **Unified Dashboard**: Central hub for all admin functions
- **Configuration Management**: Adjust settings at runtime
- **Debug Logs**: Visualize performance metrics and logs
- **RAG Analysis**: Analyze retrieval performance and relevance
- **Tool Calling Dashboard**: Monitor function calls and performance
- **Session Management**: Track user interactions and conversation history

## Running the Admin Dashboards

The admin dashboards are integrated into the main Mobeus Assistant backend. No separate repository is required.

To run the dashboards locally:

1. If you're using Docker Compose, simply start the services:

```bash
docker-compose up --build
```

2. Once the backend (and Nginx) is running, visit:

   http://127.0.0.1:8080/admin/

   This is the Main Dashboard. Use the sidebar to navigate to:
   - Configuration
   - Debug
   - Tool Calling
   - Session Management

No additional setup or cloning is required.
 
## Configuration Options

Use the **Configuration** dashboard to update runtime settings (e.g., RAG result count, memory limits).

## API Endpoints

Programmatic JSON access is available under the `/admin` prefix:
- **/**         Main Dashboard HTML
- **/config**   Configuration Dashboard HTML & API
- **/debug**    Debug Dashboard HTML & API
- **/tools**    Tool Calling Dashboard HTML & API
- **/sessions** Session Management Dashboard HTML & API