
#python#!/usr/bin/env python3
"""
Mobeus Admin Dashboard Fix Verification Script
"""
import json
from memory.db import get_connection, execute_db_operation
from memory.session_memory import get_memory_stats
from stats.session_dashboard import get_session_historical_stats, calculate_session_cost_from_db

def test_database_functions():
    """Test database function enhancements"""
    print("🧪 Testing database functions...")
    
    try:
        # Test getting sessions
        def _test_sessions():
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT DISTINCT uuid FROM session_memory LIMIT 1")
                    row = cur.fetchone()
                    return row[0] if row else None
        
        test_uuid = execute_db_operation(_test_sessions)
        
        if test_uuid:
            print(f"✅ Found test session: {test_uuid[:8]}...")
            
            # Test historical stats
            stats = get_session_historical_stats(test_uuid)
            print(f"✅ Historical stats: {stats.get('total_messages', 0)} messages")
            
            # Test cost calculation
            cost = calculate_session_cost_from_db(test_uuid)
            print(f"✅ Cost calculation: ${cost.get('total_cost', 0):.4f}")
            
            # Test memory stats
            memory = get_memory_stats(test_uuid)
            print(f"✅ Memory stats: {memory.get('session_memory_chars', 0)} chars")
            
        else:
            print("⚠️ No sessions found for testing")
            
    except Exception as e:
        print(f"❌ Database test failed: {e}")


def test_session_dashboard_functions():
    """Test session dashboard functions"""
    print("🧪 Testing session dashboard functions...")
    
    try:
        from stats.session_dashboard import get_active_sessions
        
        sessions = get_active_sessions(limit=5)
        print(f"✅ Retrieved {len(sessions)} sessions")
        
        for session in sessions[:2]:
            uuid = session.get('uuid', '')
            cost = session.get('cost_estimate', 0)
            messages = session.get('message_count', 0)
            print(f"  - {uuid[:8]}...: {messages} messages, ${cost:.4f}")
            
    except Exception as e:
        print(f"❌ Session dashboard test failed: {e}")

def main():
    """Run all verification tests"""
    print("🔧 Mobeus Admin Dashboard Fix Verification")
    print("=" * 50)
    
    test_database_functions()
    print()

    
    test_session_dashboard_functions()
    print()
    
    print("🎉 Verification complete!")
    print("\nNext steps:")
    print("1. Test voice commands in realtime chat")
    print("2. Check /admin/sessions dashboard")
    print("3. Try deep dive on a session")
    print("4. Test analyze buttons")

if __name__ == "__main__":
    main()