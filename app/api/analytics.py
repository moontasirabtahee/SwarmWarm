import logging
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends
from app.api.auth import get_current_user, TokenData
from app.core.db import INTERACTION_LOGS

logger = logging.getLogger("swarmwarm.analytics")
router = APIRouter(prefix="/api/v1/analytics", tags=["Deliverability Analytics"])

@router.get("/overview")
async def get_analytics_overview(current_user: TokenData = Depends(get_current_user)):
    """
    Aggregates rolling transaction logs to calculate placement rates and warm-up statistics.
    Filters queries strictly to the active user's tenant context.
    """
    logger.info(f"Calculating deliverability overview metrics for User: {current_user.user_id}")
    
    # Filter logs strictly belonging to the active user
    user_logs = [log for log in INTERACTION_LOGS if log["user_id"] == current_user.user_id]
    
    total_sent = 0
    spam_rescues = 0
    ai_replies = 0
    inbox_placements = 0
    
    for log in user_logs:
        action = log.get("action")
        folder = log.get("folder", "INBOX").upper()
        ai_active = log.get("ai_replied", False)
        
        if action == "sent":
             total_sent += 1
             if folder == "INBOX":
                  inbox_placements += 1
        elif action == "rescued":
             spam_rescues += 1
             inbox_placements += 1  # Rescued items end up in the Inbox!
             
        if ai_active:
             ai_replies += 1
             
    # Calculate Deliverability Placement Rate
    # Placement Rate = (Inbox Placements / (Total Sent + Spam Rescues)) * 100
    total_transactions = total_sent + spam_rescues
    placement_rate = 100.0
    if total_transactions > 0:
         placement_rate = round((inbox_placements / total_transactions) * 100, 2)
         
    return {
        "user_id": current_user.user_id,
        "metrics": {
            "total_sent_24h": total_sent,
            "spam_rescues_24h": spam_rescues,
            "ai_replies_activated_24h": ai_replies,
            "inbox_placement_rate": placement_rate
        }
    }
