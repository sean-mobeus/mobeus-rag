# Mobeus Assistant Admin Dashboard

A comprehensive admin dashboard for monitoring, debugging, and configuring the Mobeus Assistant platform.

## Features

- **Unified Dashboard**: Central hub for all admin functions
- **Configuration Management**: Easily adjust settings without code changes
- **Debug Logs**: Visualize performance metrics and logs
- **RAG Analysis**: Analyze retrieval performance and relevance
- **Tool Calling Dashboard**: Monitor function calls and performance
- **Session Management**: Track user interactions and conversation history

## Installation

### Prerequisites

- Python 3.9+ installed
- PostgreSQL database for session and memory storage
- [Optional] ChromaDB installed for RAG functionality

### Setup

1. Clone the repository:

```bash
git clone https://github.com/yourusername/mobeus-admin.git
cd mobeus-admin
```

2. Create a virtual environment and install dependencies:

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

3. Configure environment variables (create a `.env` file):

```
# Database connection
DATABASE_URL=postgresql://username:password@localhost:5432/mobeus

# OpenAI API
OPENAI_API_KEY=your-api-key-here

# Admin dashboard settings
MOBEUS_HOST=127.0.0.1
MOBEUS_PORT=8088
MOBEUS_DEBUG=true

# Session settings
SESSION_MEMORY_CHAR_LIMIT=15000
PROMPT_HISTORY_DEPTH=5
```

4. Run the application:

```bash
python main.py
```

5. Access the dashboard at: [http://127.0.0.1:8088](http://127.0.0.1:8088)

## Dashboard Modules

### Main Dashboard
The central hub providing system information and quick access to all other dashboards. Displays key system metrics and resource usage.

### Configuration Dashboard
Manage all system settings:
- Core settings (memory limits, history depth)
- Model settings (temperature, max tokens)
- Realtime voice settings (voice selection, audio format)
- RAG settings (number of results, relevance threshold)
- Turn detection settings for voice interaction

### Debug Dashboard
Visualize and analyze:
- Response time performance metrics
- Time distribution for different components
- Detailed log entries for all interactions
- System resource usage

### RAG Analysis Dashboard
Analyze retrieval performance:
- Document retrieval frequency
- Query length vs. retrieval time analysis
- Source relevance by query type
- Relevance score distribution

### Tool Calling Dashboard
Monitor function calling:
- Tool usage frequency
- Success rates by function
- Execution time analysis
- Detailed function call logs

### Session Management
Track user interactions:
- Active sessions overview
- User message history
- Session summaries
- Conversation analysis

## Directory Structure

```
mobeus-admin/
├── main.py                         # Main application entry point
├── main_dashboard.py               # Main dashboard 
├── enhanced_config_dashboard.py    # Configuration dashboard
├── enhanced_debug_dashboard.py     # Debug logs dashboard
├── rag_dashboard.py                # RAG analysis dashboard
├── tools_dashboard.py              # Tool calling dashboard
├── session_dashboard.py            # Session management dashboard
├── static/                         # Static assets (if any)
├── templates/                      # Jinja2 templates (if any)
└── requirements.txt                # Python dependencies
```

## Configuration Options

The system can be configured through:

1. **Environment variables**: Set in the `.env` file or system environment
2. **Configuration dashboard**: Runtime adjustments without restart
3. **Database settings**: Persistent configurations

## API Endpoints

Besides the HTML dashboard, the system exposes JSON API endpoints for programmatic access:

- `/config/data` - Get current configuration
- `/debug/data` - Get debug log data
- `/rag/data` - Get RAG analysis data
- `/tools/data` - Get function call data
- `/sessions/data` - Get session data
- `/sessions/{uuid}/data` - Get specific session data

## Development

To contribute to the dashboard:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/new-dashboard`)
3. Make your changes
4. Run tests (if available)
5. Submit a pull request

## Security Considerations

For production deployment, ensure:

1. Proper authentication is implemented (the current version has no auth)
2. CORS is properly configured to restrict origins
3. Sensitive environment variables are secured
4. Database credentials are protected

## Requirements

See `requirements.txt` for the full list. Key dependencies:

- fastapi
- uvicorn
- psycopg2-binary
- chromadb
- psutil
- python-dotenv
- openai
