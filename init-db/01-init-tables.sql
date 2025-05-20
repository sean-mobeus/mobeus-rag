-- init-db/01-init-tables.sql
-- Create tables for Mobeus Assistant Admin Dashboard

-- Session memory table to store conversation history
CREATE TABLE IF NOT EXISTS session_memory (
    id SERIAL PRIMARY KEY,
    uuid VARCHAR(100) NOT NULL,
    role VARCHAR(50) NOT NULL,
    message TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_uuid (uuid)
);

-- Persistent memory table to store long-term summaries
CREATE TABLE IF NOT EXISTS persistent_memory (
    uuid VARCHAR(100) PRIMARY KEY,
    summary TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Function call logs table
CREATE TABLE IF NOT EXISTS function_calls (
    id SERIAL PRIMARY KEY,
    call_id VARCHAR(100) NOT NULL,
    function_name VARCHAR(100) NOT NULL,
    arguments JSONB,
    result JSONB,
    execution_time FLOAT,
    success BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    session_uuid VARCHAR(100),
    INDEX idx_function_name (function_name),
    INDEX idx_session_uuid (session_uuid)
);

-- Configuration table for storing system settings
CREATE TABLE IF NOT EXISTS system_config (
    key VARCHAR(100) PRIMARY KEY,
    value TEXT NOT NULL,
    description TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Insert default configuration values
INSERT INTO system_config (key, value, description)
VALUES 
    ('SESSION_MEMORY_CHAR_LIMIT', '15000', 'Maximum number of characters to store in short-term session memory'),
    ('PROMPT_HISTORY_DEPTH', '5', 'Number of previous messages to include in each prompt'),
    ('GPT_MODEL', 'gpt-4', 'Model used for standard text completions'),
    ('TONE_STYLE', 'empathetic', 'Personality style for assistant responses'),
    ('TEMPERATURE', '0.7', 'Controls randomness of output')
ON CONFLICT (key) DO NOTHING;

-- Create view for recent active sessions
CREATE OR REPLACE VIEW active_sessions AS
SELECT 
    uuid,
    MAX(created_at) as last_interaction,
    COUNT(*) as message_count,
    COUNT(CASE WHEN role = 'user' THEN 1 END) as user_messages,
    COUNT(CASE WHEN role = 'assistant' THEN 1 END) as assistant_messages
FROM session_memory
GROUP BY uuid
ORDER BY last_interaction DESC;