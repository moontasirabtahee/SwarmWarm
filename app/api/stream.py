import json
import asyncio
import logging
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from app.api.auth import get_current_user, TokenData
from app.core.db import list_all_interaction_logs, list_interaction_logs_by_user

logger = logging.getLogger("swarmwarm.stream")
router = APIRouter(prefix="/api/v1/analytics", tags=["Real-Time Streams"])

async def event_generator(user_id: str, is_admin: bool):
    """
    Yields real-time Server-Sent Events (SSE) detailing database log changes
    and system status telemetry configurations.
    """
    last_seen_count = -1
    
    while True:
        try:
            # Filter logs based on role scope (admin sees all, user sees isolated)
            if is_admin:
                filtered_logs = list_all_interaction_logs()
            else:
                filtered_logs = list_interaction_logs_by_user(user_id)
                
            current_count = len(filtered_logs)
            
            # If database changes, calculate and dispatch update event
            if current_count != last_seen_count:
                last_seen_count = current_count
                
                # Calculate metrics delta
                total_sent = 0
                spam_rescues = 0
                ai_replies = 0
                inbox_placements = 0
                
                for log in filtered_logs:
                    action = log.get("action")
                    folder = log.get("folder", "INBOX").upper()
                    ai_active = log.get("ai_replied", False)
                    
                    if action == "sent":
                         total_sent += 1
                         if folder == "INBOX":
                              inbox_placements += 1
                    elif action == "rescued":
                         spam_rescues += 1
                         inbox_placements += 1
                         
                    if ai_active:
                         ai_replies += 1
                         
                total_transactions = total_sent + spam_rescues
                placement_rate = 100.0
                if total_transactions > 0:
                     placement_rate = round((inbox_placements / total_transactions) * 100, 2)
                
                # Mock system status coordinates (for Admin view)
                system_radar = {
                     "redis_backlog": max(0, 5 - total_sent % 6) if total_sent > 0 else 0,
                     "inference_speed": round(35.0 + (total_sent % 10) * 1.5, 1),
                     "hardware_temp": min(85, 55 + (total_sent % 15))
                }
                
                payload = {
                     "metrics": {
                          "total_sent_24h": total_sent,
                          "spam_rescues_24h": spam_rescues,
                          "ai_replies_activated_24h": ai_replies,
                          "inbox_placement_rate": placement_rate
                     },
                     "system_radar": system_radar,
                     # Return only the last log (which is first in a DESC sorted list) to append in real-time
                     "new_log": filtered_logs[0] if filtered_logs else None
                }
                
                yield f"data: {json.dumps(payload)}\n\n"
                
            # Poll database changes every 1.5 seconds
            await asyncio.sleep(1.5)
            
        except asyncio.CancelledError:
            logger.info(f"SSE client connection dropped for user {user_id}")
            break
        except Exception as e:
            logger.error(f"Error in SSE event generator: {e}")
            await asyncio.sleep(2.0)

@router.get("/stream")
async def stream_analytics(current_user: TokenData = Depends(get_current_user)):
    """
    Establishes a low-latency Server-Sent Events (SSE) channel pushing updates to the client.
    """
    logger.info(f"SSE Connection established for User: {current_user.user_id} (Role: {current_user.role})")
    is_admin = (current_user.role == "admin")
    
    return StreamingResponse(
        event_generator(current_user.user_id, is_admin),
        media_type="text/event-stream"
    )
