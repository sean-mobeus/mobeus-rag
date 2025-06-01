"""
Voice command detection and handling utilities.
"""

def detect_summary_request(message_text: str) -> bool:
    """
    Enhanced detection of user requesting conversation summary with comprehensive logging.
    """
    if not message_text or not isinstance(message_text, str):
        return False

    summary_triggers = [
        "summarize our conversation",
        "summarize what we discussed",
        "give me a summary",
        "summarize this conversation",
        "create a summary",
        "can you summarize",
        "summarize what we talked about",
        "sum up our chat",
        "recap our conversation",
        "make a summary",
        "provide a summary",
        "conversation summary",
        "recap what we discussed",
        "sum up what we said",
        "give me a recap"
    ]

    message_lower = message_text.lower().strip()

    for trigger in summary_triggers:
        if trigger in message_lower:
            print(f"🎯 VOICE COMMAND DETECTED: '{trigger}' in message: '{message_text[:100]}...'")
            return True

    summary_keywords = ["summary", "summarize", "recap", "sum up"]
    if any(keyword in message_lower for keyword in summary_keywords):
        print(f"🎯 VOICE COMMAND DETECTED (keyword): '{message_text[:100]}...'")
        return True

    return False


def handle_summary_request(
    message_text: str,
    memory_client,
    user_uuid: str,
    send_json,
    modalities=None,
    confirmation_text: str = None,
    error_text: str = None,
) -> bool:
    """
    Detect a summary request in message_text. If triggered, force a session summary
    via memory_client and emit the appropriate system and response messages
    through send_json. Returns True if the request was handled (short-circuited).
    """
    if not detect_summary_request(message_text):
        return False

    # Force summary in persistent memory
    success = memory_client.force_session_summary(
        user_uuid, "user_requested_mid_session"
    )

    # Prepare default messages if not provided
    if success:
        msg = (
            confirmation_text
            or "I've created a summary of our conversation and stored it in your persistent memory."
        )
    else:
        msg = (
            error_text
            or "I wasn't able to create a summary right now. There might not be enough content yet."
        )

    # Emit system message confirming or reporting error
    system_event = {
        "type": "conversation.item.create",
        "item": {
            "type": "message",
            "role": "system",
            "content": [{"type": "input_text", "text": msg}]
        }
    }
    send_json(system_event)

    # Resume assistant response if modalities specified
    if modalities:
        resume_event = {"type": "response.create", "response": {"modalities": modalities}}
        send_json(resume_event)

    return True