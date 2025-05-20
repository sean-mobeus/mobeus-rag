"""
Database module that centralizes all database connection and initialization logic
"""
import psycopg2
import os
from datetime import datetime
from typing import Optional
import traceback

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
        # Initialize all tables
        init_persistent_memory_table()
        init_session_table()
        init_user_table()
        
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