import json
import asyncio
import logging
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from app.api.auth import get_current_user, TokenData
from app.core.db import (
    list_all_interaction_logs,
    aggregate_metrics_by_user,
    count_interaction_logs_by_user,
    get_latest_interaction_log_by_user,
)

logger = logging.getLogger("swarmwarm.stream")
router = APIRouter(prefix="/api/v1/analytics", tags=["Real-Time Streams"])


def _gather(user_id: str, is_admin: bool):
    """
    Returns (log_count, metrics_dict, latest_log) for the current scope.

    User scope aggregates in SQL (no rows pulled into Python each poll). Admin scope
    keeps the existing "most recent 100" semantics by aggregating that bounded set.
    """
    if is_admin:
        logs = list_all_interaction_logs()
        total_sent = spam_rescues = ai_replies = inbox_placements = 0
        for log in logs:
            action = log.get("action")
            folder = (log.get("folder") or "INBOX").upper()
            if action == "sent":
                total_sent += 1
                if folder == "INBOX":
                    inbox_placements += 1
            elif action == "rescued":
                spam_rescues += 1
                inbox_placements += 1
            if log.get("ai_replied"):
                ai_replies += 1
        metrics = {"total_sent": total_sent, "spam_rescues": spam_rescues,
                   "ai_replies": ai_replies, "inbox_placements": inbox_placements}
        return len(logs), metrics, (logs[0] if logs else None)

    return (
        count_interaction_logs_by_user(user_id),
        aggregate_metrics_by_user(user_id),
        get_latest_interaction_log_by_user(user_id),
    )


async def event_generator(user_id: str, is_admin: bool):
    """
    Yields real-time Server-Sent Events (SSE) detailing database log changes
    and system status telemetry configurations.
    """
    last_seen_count = -1

    while True:
        try:
            current_count, metrics, latest_log = _gather(user_id, is_admin)

            # If database changes, calculate and dispatch update event
            if current_count != last_seen_count:
                last_seen_count = current_count

                total_sent = metrics["total_sent"]
                spam_rescues = metrics["spam_rescues"]
                ai_replies = metrics["ai_replies"]
                inbox_placements = metrics["inbox_placements"]

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
                     # Most recent log (DESC order) to append in real-time
                     "new_log": latest_log
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
