"""
Database module that centralizes all database connection and initialization logic
"""
import psycopg2
import os, json
from datetime import datetime
from typing import Optional, Dict, Any, List
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
    """Enhanced table initialization including new tables"""
    global _tables_initialized
    
    if _tables_initialized:
        return True
    
    try:
        # Initialize all existing tables
        init_persistent_memory_table()
        init_session_table()
        init_user_table()
        init_session_prompts_table()
        init_summarization_events_table()
        init_interaction_logs_table()
        
        # Initialize new tables
        init_voice_commands_table()
        init_session_metadata_table()
        
        _tables_initialized = True
        print("✅ All database tables initialized successfully (including voice commands and session metadata)")
        return True
    except Exception as e:
        print(f"⚠️ Database initialization error: {e}")
        traceback.print_exc()
        return False

print("🔧 Enhanced database functions loaded with session metadata and voice command tracking")

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

def init_voice_commands_table():
    """Initialize the voice_commands table for tracking voice command usage"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS voice_commands (
                    id SERIAL PRIMARY KEY,
                    uuid TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    command_type VARCHAR(100),
                    success BOOLEAN,
                    reason TEXT,
                    user_message TEXT,
                    response_sent TEXT
                );
            """)
            
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_voice_commands_uuid 
                ON voice_commands(uuid);
            """)
            conn.commit()

def init_session_metadata_table():
    """Initialize session metadata table for persistent session stats"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS session_metadata (
                    uuid TEXT PRIMARY KEY,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    
                    -- Session statistics
                    total_messages INTEGER DEFAULT 0,
                    total_user_messages INTEGER DEFAULT 0,
                    total_assistant_messages INTEGER DEFAULT 0,
                    total_characters INTEGER DEFAULT 0,
                    
                    -- Cost tracking
                    total_input_tokens INTEGER DEFAULT 0,
                    total_output_tokens INTEGER DEFAULT 0,
                    estimated_cost DECIMAL(10,6) DEFAULT 0.0,
                    
                    -- Session timing
                    first_interaction TIMESTAMP,
                    last_interaction TIMESTAMP,
                    total_duration_minutes INTEGER DEFAULT 0,
                    
                    -- Memory management
                    summarization_count INTEGER DEFAULT 0,
                    current_memory_chars INTEGER DEFAULT 0,
                    persistent_memory_chars INTEGER DEFAULT 0,
                    
                    -- Configuration at time of session
                    strategy VARCHAR(50) DEFAULT 'auto',
                    model VARCHAR(100),
                    voice VARCHAR(50),
                    
                    -- Session status
                    status VARCHAR(20) DEFAULT 'active'
                );
            """)
            
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_session_metadata_updated_at 
                ON session_metadata(updated_at DESC);
            """)
            
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_session_metadata_status 
                ON session_metadata(status);
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

def update_session_metadata(uuid: str, **kwargs):
    """Update session metadata with provided values"""
    def _update_impl():
        with get_connection() as conn:
            with conn.cursor() as cur:
                # First check if record exists
                cur.execute("SELECT uuid FROM session_metadata WHERE uuid = %s", (uuid,))
                exists = cur.fetchone()
                
                if not exists:
                    # Create new record
                    cur.execute("""
                        INSERT INTO session_metadata (uuid, updated_at)
                        VALUES (%s, CURRENT_TIMESTAMP)
                    """, (uuid,))
                
                # Update provided fields
                update_fields = []
                update_values = []
                
                for field, value in kwargs.items():
                    if field in ['total_messages', 'total_user_messages', 'total_assistant_messages', 
                                 'total_characters', 'total_input_tokens', 'total_output_tokens',
                                 'estimated_cost', 'total_duration_minutes', 'summarization_count',
                                 'current_memory_chars', 'persistent_memory_chars', 'strategy',
                                 'model', 'voice', 'status', 'first_interaction', 'last_interaction']:
                        update_fields.append(f"{field} = %s")
                        update_values.append(value)
                
                if update_fields:
                    update_fields.append("updated_at = CURRENT_TIMESTAMP")
                    update_values.append(uuid)
                    
                    query = f"""
                        UPDATE session_metadata 
                        SET {', '.join(update_fields)}
                        WHERE uuid = %s
                    """
                    cur.execute(query, update_values)
                
                conn.commit()
    
    execute_db_operation(_update_impl)

def get_session_metadata(uuid: str) -> Dict[str, Any]:
    """Get session metadata for a specific session"""
    def _get_impl():
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT 
                        total_messages, total_user_messages, total_assistant_messages,
                        total_characters, total_input_tokens, total_output_tokens,
                        estimated_cost, first_interaction, last_interaction,
                        total_duration_minutes, summarization_count, current_memory_chars,
                        persistent_memory_chars, strategy, model, voice, status,
                        created_at, updated_at
                    FROM session_metadata
                    WHERE uuid = %s
                """, (uuid,))
                
                row = cur.fetchone()
                if row:
                    return {
                        'total_messages': row[0] or 0,
                        'total_user_messages': row[1] or 0,
                        'total_assistant_messages': row[2] or 0,
                        'total_characters': row[3] or 0,
                        'total_input_tokens': row[4] or 0,
                        'total_output_tokens': row[5] or 0,
                        'estimated_cost': float(row[6]) if row[6] else 0.0,
                        'first_interaction': row[7].isoformat() if row[7] else None,
                        'last_interaction': row[8].isoformat() if row[8] else None,
                        'total_duration_minutes': row[9] or 0,
                        'summarization_count': row[10] or 0,
                        'current_memory_chars': row[11] or 0,
                        'persistent_memory_chars': row[12] or 0,
                        'strategy': row[13] or 'auto',
                        'model': row[14] or 'unknown',
                        'voice': row[15] or 'unknown',
                        'status': row[16] or 'active',
                        'created_at': row[17].isoformat() if row[17] else None,
                        'updated_at': row[18].isoformat() if row[18] else None
                    }
                return {}
    
    return execute_db_operation(_get_impl) or {}

def calculate_and_store_session_stats(uuid: str):
    """Calculate comprehensive session statistics and store in metadata table"""
    def _calculate_impl():
        with get_connection() as conn:
            with conn.cursor() as cur:
                # Get current session stats
                cur.execute("""
                    SELECT 
                        COUNT(*) as total_messages,
                        COUNT(CASE WHEN role = 'user' THEN 1 END) as user_messages,
                        COUNT(CASE WHEN role = 'assistant' THEN 1 END) as assistant_messages,
                        SUM(LENGTH(message)) as total_chars,
                        MIN(created_at) as first_msg,
                        MAX(created_at) as last_msg
                    FROM session_memory
                    WHERE uuid = %s
                """, (uuid,))
                
                current_stats = cur.fetchone()
                
                # Get historical interaction stats
                cur.execute("""
                    SELECT 
                        COUNT(*) as historical_interactions,
                        SUM(LENGTH(COALESCE(user_message, '') + COALESCE(assistant_response, ''))) as historical_chars
                    FROM interaction_logs
                    WHERE uuid = %s
                """, (uuid,))
                
                historical_stats = cur.fetchone()
                
                # Get summarization count
                cur.execute("""
                    SELECT COUNT(*) FROM summarization_events WHERE uuid = %s
                """, (uuid,))
                
                summarization_count = cur.fetchone()[0] or 0
                
                # Get persistent memory size
                from memory.persistent_memory import get_summary
                persistent_summary = get_summary(uuid)
                persistent_chars = len(persistent_summary) if persistent_summary else 0
                
                # Calculate totals
                total_messages = (current_stats[0] or 0) + (historical_stats[0] or 0) * 2
                total_user_messages = (current_stats[1] or 0) + (historical_stats[0] or 0)
                total_assistant_messages = (current_stats[2] or 0) + (historical_stats[0] or 0)
                total_characters = (current_stats[3] or 0) + (historical_stats[1] or 0)
                
                # Calculate duration
                first_interaction = current_stats[4]
                last_interaction = current_stats[5]
                duration_minutes = 0
                
                if first_interaction and last_interaction:
                    duration = last_interaction - first_interaction
                    duration_minutes = int(duration.total_seconds() / 60)
                
                # Estimate cost (rough calculation)
                estimated_tokens = total_characters // 4
                estimated_cost = (estimated_tokens / 1000) * 0.01  # Rough estimate
                
                # Update metadata
                update_session_metadata(uuid,
                    total_messages=total_messages,
                    total_user_messages=total_user_messages,
                    total_assistant_messages=total_assistant_messages,
                    total_characters=total_characters,
                    estimated_cost=estimated_cost,
                    first_interaction=first_interaction,
                    last_interaction=last_interaction,
                    total_duration_minutes=duration_minutes,
                    summarization_count=summarization_count,
                    current_memory_chars=current_stats[3] or 0,
                    persistent_memory_chars=persistent_chars
                )
                
                print(f"✅ Updated session metadata for {uuid}: {total_messages} messages, {duration_minutes} min")
                return {
                    'total_messages': total_messages,
                    'estimated_cost': estimated_cost,
                    'duration_minutes': duration_minutes
                }
    
    return execute_db_operation(_calculate_impl) or {}

def log_voice_command_to_db(uuid: str, command_type: str, success: bool, reason: str = "", user_message: str = "", response_sent: str = ""):
    """Log voice command to database"""
    def _log_impl():
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO voice_commands 
                    (uuid, command_type, success, reason, user_message, response_sent)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (uuid, command_type, success, reason, user_message, response_sent))
                conn.commit()
    
    execute_db_operation(_log_impl)
    print(f"📝 Voice command logged: {command_type} for {uuid} - Success: {success}")

def get_voice_command_history(uuid: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Get voice command history for a session"""
    def _get_impl():
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT created_at, command_type, success, reason, user_message, response_sent
                    FROM voice_commands
                    WHERE uuid = %s
                    ORDER BY created_at DESC
                    LIMIT %s
                """, (uuid, limit))
                
                commands = []
                for row in cur.fetchall():
                    commands.append({
                        'timestamp': row[0].isoformat() if row[0] else None,
                        'command_type': row[1],
                        'success': row[2],
                        'reason': row[3],
                        'user_message': row[4],
                        'response_sent': row[5]
                    })
                
                return commands
    
    return execute_db_operation(_get_impl) or []

def migrate_session_metadata():
    """One-time migration to populate session metadata table"""
    print("🚀 Starting session metadata migration...")
    
    try:
        # Get all unique sessions
        def _get_all_sessions():
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT DISTINCT uuid FROM session_memory 
                        UNION 
                        SELECT DISTINCT uuid FROM interaction_logs
                        UNION
                        SELECT DISTINCT uuid FROM persistent_memory
                    """)
                    return [row[0] for row in cur.fetchall()]
        
        all_sessions = execute_db_operation(_get_all_sessions) or []
        print(f"📊 Found {len(all_sessions)} unique sessions to migrate")
        
        # Calculate stats for each session
        migrated_count = 0
        for uuid in all_sessions:
            try:
                stats = calculate_and_store_session_stats(uuid)
                if stats:
                    migrated_count += 1
                    if migrated_count % 10 == 0:
                        print(f"📈 Migrated {migrated_count}/{len(all_sessions)} sessions...")
            except Exception as e:
                print(f"⚠️ Error migrating session {uuid}: {e}")
                continue
        
        print(f"🎉 Session metadata migration complete! Migrated {migrated_count} sessions")
        return migrated_count
        
    except Exception as e:
        print(f"❌ Session metadata migration failed: {e}")
        import traceback
        traceback.print_exc()
        return 0
