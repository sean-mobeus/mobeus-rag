# routes/openai_realtime_tokens.py
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional

# Add request models for tools
class SearchKnowledgeBaseRequest(BaseModel):
    query: str
    user_uuid: Optional[str] = None

class UpdateUserMemoryRequest(BaseModel):
    information: str
    user_uuid: str
import httpx
from config.config import OPENAI_API_KEY
from config.openaiconfig import (
    REALTIME_VOICES,
    REALTIME_MODELS,
    DEFAULT_REALTIME_CONFIG
)
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

# OpenAI Realtime Session endpoint
OPENAI_REALTIME_SESSIONS_URL = "https://api.openai.com/v1/realtime/sessions"

class EphemeralTokenRequest(BaseModel):
    user_uuid: Optional[str] = None
    model: str = "gpt-4o-realtime-preview-2024-12-17"
    voice: str = "alloy"  # Changed from "nova" to "alloy"
    instructions: Optional[str] = None

class EphemeralTokenResponse(BaseModel):
    client_secret: dict
    id: str  # OpenAI returns 'id', not 'session_id'
    expires_at: int  # OpenAI returns timestamp as integer
    
    # Optional - we can add a computed property for easier access
    @property
    def session_id(self):
        return self.id
    
    @property
    def expires_at_iso(self):
        from datetime import datetime
        return datetime.fromtimestamp(self.expires_at).isoformat()

@router.post("/api/realtime/session", response_model=EphemeralTokenResponse)
async def create_realtime_session(request: EphemeralTokenRequest):
    """
    Create an ephemeral token for OpenAI Realtime API.
    This token allows the frontend to connect directly to OpenAI via WebRTC.
    """
    try:
        # Get user context for custom instructions
        user_instructions = get_user_instructions(request.user_uuid, request.instructions)
        
        # Prepare the session request
        session_data = {
            "model": request.model,
            "voice": request.voice,
            "modalities": ["text", "audio"],
            "instructions": user_instructions,
            "input_audio_format": "pcm16",
            "output_audio_format": "pcm16",
            "input_audio_transcription": {
                "model": "whisper-1"
            },
            "turn_detection": {
                "type": "server_vad",
                "threshold": 0.5,
                "prefix_padding_ms": 300,
                "silence_duration_ms": 200
            },
            "tools": [
                {
                    "type": "function",
                    "name": "search_knowledge_base",
                    "description": "Search the Mobeus knowledge base for relevant information to answer user questions",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "The search query to find relevant information"
                            }
                        },
                        "required": ["query"]
                    }
                },
                {
                    "type": "function",
                    "name": "update_user_memory",
                    "description": "Store important information about the user for future conversations",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "information": {
                                "type": "string",
                                "description": "Important information to remember about the user"
                            },
                            "user_uuid": {
                                "type": "string",
                                "description": "The user's UUID"
                            }
                        },
                        "required": ["information", "user_uuid"]
                    }
                }
            ]
        }
        
        # Make request to OpenAI
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                OPENAI_REALTIME_SESSIONS_URL,
                headers={
                    "Authorization": f"Bearer {OPENAI_API_KEY}",
                    "Content-Type": "application/json"
                },
                json=session_data
            )
            
            response.raise_for_status()
            session_info = response.json()
            
            # Debug: log what OpenAI actually returns
            logger.info(f"OpenAI response: {session_info}")
            
            logger.info(f"Created ephemeral token for user {request.user_uuid}")
            
            return EphemeralTokenResponse(**session_info)
            
    except httpx.HTTPStatusError as e:
        logger.error(f"OpenAI API error: {e.response.status_code} - {e.response.text}")
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"OpenAI API error: {e.response.text}"
        )
    except Exception as e:
        logger.error(f"Error creating ephemeral token: {e}")
        import traceback
        traceback.print_exc()  # This will help us see the full error
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create realtime session: {str(e)}"
        )

def get_user_instructions(user_uuid: Optional[str], base_instructions: Optional[str] = None) -> str:
    """Generate personalized instructions based on user context"""
    
    # Base instructions
    instructions = base_instructions or """You are Mobeus Assistant, a helpful AI assistant.

Key behaviors:
- Be conversational and friendly
- Keep responses concise unless asked for details
- Use the search_knowledge_base tool when you need specific information
- Remember important user information using update_user_memory tool
- Always try to be helpful and provide accurate information

"""
    
    # Add user-specific context if available
    if user_uuid:
        try:
            # Import the actual functions (not the route handlers)
            from memory.user_identity import get_user
            from memory.persistent_memory import get_summary
            from memory.session_memory import get_all_session_memory
            
            # Get user information
            user = get_user(user_uuid)
            if user and user.get('name'):
                instructions += f"The user's name is {user['name']}. "
            
            # Add recent conversation context
            recent = get_all_session_memory(user_uuid)
            if recent:
                instructions += "\nRecent conversation context:\n"
                for item in recent:
                    instructions += f"{item['role'].title()}: {item['message']}\n"
                    
            # Add long-term memory
            summary = get_summary(user_uuid)
            if summary:
                instructions += f"\nWhat you know about this user: {summary}\n"
                
        except Exception as e:
            logger.warning(f"Could not load user context: {e}")
    
    return instructions

# Tool execution endpoints - these will be called by the frontend
# when OpenAI requests tool execution

@router.post("/api/realtime/tools/search_knowledge_base")
async def search_knowledge_base_tool(request: SearchKnowledgeBaseRequest):
    """Execute knowledge base search for OpenAI Realtime API"""
    try:
        from vector.rag import retrieve_documents
        
        # Perform RAG search
        documents = await retrieve_documents(request.query)
        
        # Format results
        search_results = []
        for doc in documents[:3]:  # Limit to top 3 results
            search_results.append({
                "content": doc["text"],
                "source": doc.get("source", "Unknown"),
                "relevance_score": doc.get("score", 0)
            })
        
        # Log the interaction if user_uuid is provided
        if request.user_uuid:
            from memory.session_memory import log_interaction
            log_interaction(request.user_uuid, "system", f"Searched knowledge base for: {request.query}")
        
        return {
            "results": search_results,
            "query": request.query,
            "total_results": len(documents)
        }
        
    except Exception as e:
        logger.error(f"Error in knowledge base search: {e}")
        return {
            "error": str(e),
            "results": [],
            "query": request.query
        }

@router.post("/api/realtime/tools/update_user_memory")
async def update_user_memory_tool(request: UpdateUserMemoryRequest):
    """Update user memory for OpenAI Realtime API"""
    try:
        from memory.persistent_memory import append_to_summary
        
        # Append new information to user's long-term memory
        append_to_summary(request.user_uuid, request.information)
        
        # Also log as an interaction
        from memory.session_memory import log_interaction
        log_interaction(request.user_uuid, "system", f"Updated memory: {request.information}")
        
        return {
            "success": True,
            "message": "User memory updated successfully"
        }
        
    except Exception as e:
        logger.error(f"Error updating user memory: {e}")
        return {
            "success": False,
            "error": str(e)
        }

# Helper endpoint to get session status
@router.get("/api/realtime/status")
async def get_realtime_status():
    """Get status of Realtime API integration"""
    return {
        "service": "OpenAI Realtime API",
        "connection_method": "WebRTC",
        "available_models": REALTIME_MODELS,
        "available_voices": REALTIME_VOICES,
        "tools_available": [
            "search_knowledge_base",
            "update_user_memory"
        ],
        "default_config": DEFAULT_REALTIME_CONFIG
    }