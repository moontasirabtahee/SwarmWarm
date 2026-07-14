import logging
from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from pydantic import BaseModel

from app.api.auth import get_current_user, TokenData
from app.core.db import aggregate_metrics_by_user

logger = logging.getLogger("swarmwarm.analytics")

router = APIRouter(prefix="/api/v1/analytics", tags=["Deliverability Analytics"])
dashboard_router = APIRouter(prefix="/api/v1", tags=["Dashboard Statistics"])

class MetricDetails(BaseModel):
    total_sent_24h: int
    spam_rescues_24h: int
    ai_replies_activated_24h: int
    inbox_placement_rate: float

class AnalyticsOverviewResponse(BaseModel):
    user_id: str
    metrics: MetricDetails

@router.get("/overview", response_model=AnalyticsOverviewResponse)
@dashboard_router.get("/dashboard/stats", response_model=AnalyticsOverviewResponse)
async def get_analytics_overview(current_user: TokenData = Depends(get_current_user)):
    """
    Aggregates rolling transaction logs to calculate placement rates and warm-up statistics.
    Filters queries strictly to the active user's tenant context.
    """
    logger.info(f"Calculating deliverability overview metrics for User: {current_user.user_id}")

    # Aggregate strictly within the active user's tenant context (computed in SQL).
    m = aggregate_metrics_by_user(current_user.user_id)

    total_transactions = m["total_sent"] + m["spam_rescues"]
    placement_rate = 100.0
    if total_transactions > 0:
        placement_rate = round((m["inbox_placements"] / total_transactions) * 100, 2)

    return AnalyticsOverviewResponse(
        user_id=current_user.user_id,
        metrics=MetricDetails(
            total_sent_24h=m["total_sent"],
            spam_rescues_24h=m["spam_rescues"],
            ai_replies_activated_24h=m["ai_replies"],
            inbox_placement_rate=placement_rate
        )
    )
