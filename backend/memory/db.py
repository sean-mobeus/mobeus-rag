"""
Database module that centralizes all database connection and initialization logic
"""
import psycopg2
import os, json
from datetime import datetime
from typing import Optional
import traceback
from config import LOG_DIR


# Centralized database connection parameters
DB_PARAMS = {
    "host": os.getenv("POSTGRES_HOST", "localhost"),
    "port": os.getenv("POSTGRES_PORT", 5432),
    "dbname": os.getenv("POSTGRES_DB", "mobeus"),
    "user": os.getenv("POSTGRES_USER", "postgres"),
    "password": os.getenv("POSTGRES_PASSWORD", "password")
}

# Flag to track initialization state
_tables_initialized = False

def get_connection():
    """Get a connection to the PostgreSQL database"""
    try:
        return psycopg2.connect(**DB_PARAMS)
    except Exception as e:
        print(f"⚠️ Database connection error: {e}")
        raise

def ensure_tables_exist():
    """
    Ensure that all required database tables exist.
    This is called during FastAPI startup and before any database operation.
    """
    global _tables_initialized
    
    # Skip if already initialized
    if _tables_initialized:
        return True
    
    try:
        # Initialize all tables (EXISTING)
        init_persistent_memory_table()
        init_session_table()
        init_user_table()
        init_session_prompts_table()
        init_summarization_events_table()
        init_interaction_logs_table()
        
        _tables_initialized = True
        print("✅ All database tables initialized successfully")
        return True
    except Exception as e:
        print(f"⚠️ Database initialization error: {e}")
        traceback.print_exc()
        return False

def init_persistent_memory_table():
    """Initialize the persistent_memory table"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS persistent_memory (
                    uuid TEXT PRIMARY KEY,
                    summary TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            conn.commit()

def init_session_table():
    """Initialize the session_memory table"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS session_memory (
                    id SERIAL PRIMARY KEY,
                    uuid TEXT NOT NULL,
                    role TEXT NOT NULL,
                    message TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            conn.commit()

def init_user_table():
    """Initialize the users table"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    uuid TEXT PRIMARY KEY,
                    name TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            conn.commit()

def init_session_prompts_table():
    """Initialize the session_prompts table for storing actual prompts"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS session_prompts (
                    id SERIAL PRIMARY KEY,
                    uuid TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    system_prompt TEXT,
                    persistent_summary TEXT,
                    session_context TEXT,
                    final_prompt TEXT,
                    prompt_length INTEGER,
                    estimated_tokens INTEGER,
                    strategy VARCHAR(50),
                    model VARCHAR(100)
                );
            """)
            
            # Create index for faster lookups
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_session_prompts_uuid 
                ON session_prompts(uuid);
            """)
            conn.commit()

def init_summarization_events_table():
    """Initialize the summarization_events table"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS summarization_events (
                    id SERIAL PRIMARY KEY,
                    uuid TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    event_type VARCHAR(100),
                    trigger_reason VARCHAR(255),
                    conversation_length INTEGER,
                    summary_generated TEXT,
                    chars_before INTEGER,
                    chars_after INTEGER,
                    details JSONB
                );
            """)
            
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_summarization_events_uuid 
                ON summarization_events(uuid);
            """)
            conn.commit()

def execute_db_operation(operation_func, *args, **kwargs):
    """
    Wrapper for database operations with automatic table initialization
    and error handling
    """
    # Ensure tables exist before attempting any operations
    if not _tables_initialized:
        ensure_tables_exist()
        
    try:
        return operation_func(*args, **kwargs)
    except psycopg2.errors.UndefinedTable:
        # If we hit an undefined table error, force table initialization
        print("⚠️ Table doesn't exist, reinitializing...")
        ensure_tables_exist()
        # Try the operation again
        return operation_func(*args, **kwargs)
    except Exception as e:
        print(f"⚠️ Database operation error: {e}")
        traceback.print_exc()
        raise

def init_interaction_logs_table():
    """Initialize the interaction_logs table for detailed interaction analysis"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS interaction_logs (
                    id SERIAL PRIMARY KEY,
                    uuid TEXT NOT NULL,
                    interaction_id TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    
                    user_message TEXT,
                    assistant_response TEXT,
                    rag_context TEXT,
                    strategy VARCHAR(50),
                    model VARCHAR(100),
                    final_prompt TEXT,
                    estimated_tokens INTEGER,
                    tools_called TEXT
                );
            """)
            
            # Index for fast lookups
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_interaction_logs_uuid 
                ON interaction_logs(uuid);
            """)
            
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_interaction_logs_created_at 
                ON interaction_logs(created_at DESC);
            """)
            conn.commit()

def migrate_existing_logs_to_db():
    """Quick migration of existing logs - one-time run"""
    
    print("🚀 Starting migration of existing logs...")
    migrated_count = 0
    
    try:
        # Get all existing sessions from session_memory
        def _get_existing_sessions():
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT DISTINCT uuid FROM session_memory 
                        ORDER BY uuid
                    """)
                    return [row[0] for row in cur.fetchall()]
        
        sessions = execute_db_operation(_get_existing_sessions) or []
        print(f"📊 Found {len(sessions)} existing sessions to migrate")
        
        # Read existing prompt data
        prompts_data = {}
        prompts_file = os.path.join(LOG_DIR, "actual_prompts.jsonl")
        if os.path.exists(prompts_file):
            with open(prompts_file, "r") as f:
                for line in f:
                    try:
                        entry = json.loads(line)
                        uuid = entry.get("user_uuid")
                        if uuid:
                            prompts_data[uuid] = entry
                    except:
                        continue
        
        print(f"📝 Found prompt data for {len(prompts_data)} sessions")
        
        from .session_memory import get_all_session_memory

        # For each session, create interaction log entries
        for uuid in sessions:
            try:
                # Get conversation for this session
                conversation = get_all_session_memory(uuid)
                if not conversation:
                    continue
                
                # Get prompt data if available
                prompt_info = prompts_data.get(uuid, {})
                
                # Create interaction pairs (user + assistant)
                interactions = []
                current_user_msg = None
                
                for msg in conversation:
                    if msg["role"] == "user":
                        current_user_msg = msg["message"]
                    elif msg["role"] == "assistant" and current_user_msg:
                        interactions.append({
                            "user_message": current_user_msg,
                            "assistant_response": msg["message"],
                            "created_at": msg["created_at"]
                        })
                        current_user_msg = None
                
                # Store interaction logs
                for i, interaction in enumerate(interactions):
                    interaction_id = f"{uuid}_{i+1}"
                    
                    def _store_interaction():
                        with get_connection() as conn:
                            with conn.cursor() as cur:
                                cur.execute("""
                                    INSERT INTO interaction_logs 
                                    (uuid, interaction_id, user_message, assistant_response, 
                                     rag_context, strategy, model, final_prompt, estimated_tokens, 
                                     tools_called, created_at)
                                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                                """, (
                                    uuid,
                                    interaction_id,
                                    interaction["user_message"],
                                    interaction["assistant_response"],
                                    "Legacy data - RAG context not available",
                                    prompt_info.get("strategy", "auto"),
                                    prompt_info.get("model", "unknown"),
                                    prompt_info.get("final_prompt", "")[:1000],  # Truncate if too long
                                    prompt_info.get("estimated_tokens", 0),
                                    "Legacy data - no tool info",
                                    interaction["created_at"]
                                ))
                                conn.commit()
                    
                    execute_db_operation(_store_interaction)
                    migrated_count += 1
                
                print(f"✅ Migrated {len(interactions)} interactions for session {uuid[:8]}...")
                
            except Exception as e:
                print(f"⚠️ Error migrating session {uuid}: {e}")
                continue
        
        print(f"🎉 Migration complete! Migrated {migrated_count} interactions")
        return migrated_count
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return 0



