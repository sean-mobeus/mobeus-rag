# Save this as ensure_logs.py in your backend directory

import os
import json
import datetime

def ensure_log_file_exists():
    """
    Ensure log file exists on application startup.
    Place this in your FastAPI startup code.
    """
    try:
        # Import config to get the path
        from config import DEBUG_LOG_PATH
        
        # Create directory if needed
        log_dir = os.path.dirname(DEBUG_LOG_PATH)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)
            print(f"📁 Created log directory: {log_dir}")
        
        # Create file if it doesn't exist
        if not os.path.exists(DEBUG_LOG_PATH):
            with open(DEBUG_LOG_PATH, "a") as f:
                startup_entry = {
                    "timestamp": datetime.datetime.now().isoformat(),
                    "message": "Application startup - log file initialized",
                    "query": "system",
                    "top_chunks": [],
                    "answer": "System startup",
                    "timings": {"total": 0.0}
                }
                f.write(json.dumps(startup_entry) + "\n")
            print(f"📝 Created log file: {DEBUG_LOG_PATH}")
        else:
            print(f"✅ Log file already exists: {DEBUG_LOG_PATH}")
            
        # Write startup entry regardless
        with open(DEBUG_LOG_PATH, "a") as f:
            startup_entry = {
                "timestamp": datetime.datetime.now().isoformat(),
                "message": "Application startup",
                "query": "system",
                "top_chunks": [],
                "answer": "System startup",
                "timings": {"total": 0.0}
            }
            f.write(json.dumps(startup_entry) + "\n")
            
        print(f"✅ Added startup entry to log file")
        return True
    except Exception as e:
        print(f"❌ Error ensuring log file exists: {e}")
        return False

if __name__ == "__main__":
    # Test the function directly
    ensure_log_file_exists()