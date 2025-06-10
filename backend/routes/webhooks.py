from fastapi import APIRouter, Request
from typing import Dict, Any
import json
import asyncio

router = APIRouter()

# Store pending webhook callbacks as queues
webhook_callbacks: Dict[str, asyncio.Queue] = {}

@router.post("/webhooks/did/{talk_id}")
async def did_webhook(talk_id: str, request: Request):
    """Handle D-ID webhook callback"""
    payload = await request.json()
    print(f"🎬 D-ID webhook received for {talk_id}: status={payload.get('status')}")
    
    # Put result in queue if someone is waiting
    if talk_id in webhook_callbacks:
        print(f"📥 Putting webhook result in queue for {talk_id}")
        await webhook_callbacks[talk_id].put(payload)
        print(f"✅ Webhook result queued for {talk_id}")
    else:
        print(f"⚠️ No queue waiting for webhook {talk_id}")
    
    return {"status": "ok"}

def create_webhook_queue(talk_id: str) -> asyncio.Queue:
    """Create a queue to wait for webhook"""
    queue = asyncio.Queue(maxsize=1)
    webhook_callbacks[talk_id] = queue
    
    # Clean up after 30 seconds
    async def cleanup():
        await asyncio.sleep(30)
        if talk_id in webhook_callbacks:
            del webhook_callbacks[talk_id]
    
    asyncio.create_task(cleanup())
    return queue