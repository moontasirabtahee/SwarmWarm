import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.api.auth import get_current_user, TokenData
from app.core.db import (
    list_all_mailboxes,
    get_all_users,
    list_system_logs,
    list_all_interaction_logs
)

logger = logging.getLogger("swarmwarm.admin")
router = APIRouter(prefix="/api/v1/admin", tags=["Admin Control Radar"])

# Pydantic responses for admin schemas
class AdminStatsResponse(BaseModel):
    total_sent_24h: int
    spam_rescues_24h: int
    active_node_count: int

class AdminMailboxResponse(BaseModel):
    id: str
    user_id: str
    email: str
    provider: str
    is_active: bool

class AdminUserResponse(BaseModel):
    id: str
    email: str
    role: str

class SystemLogResponse(BaseModel):
    id: str
    timestamp: str
    module: str
    event: str
    level: str

# Guard dependency to verify admin scope
def require_admin(current_user: TokenData = Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Administrative privileges required."
        )
    return current_user

@router.get("/dashboard/stats", response_model=AdminStatsResponse)
async def get_admin_dashboard_stats(_: TokenData = Depends(require_admin)):
    """
    Returns global cross-tenant warmup metrics and active node counts.
    """
    all_logs = list_all_interaction_logs()
    all_mailboxes = list_all_mailboxes()
    
    total_sent = sum(1 for log in all_logs if log["action"] == "sent")
    spam_rescues = sum(1 for log in all_logs if log["action"] == "rescued")
    active_nodes = sum(1 for m in all_mailboxes if m["is_active"])
    
    return AdminStatsResponse(
        total_sent_24h=total_sent,
        spam_rescues_24h=spam_rescues,
        active_node_count=active_nodes
    )

@router.get("/mailboxes", response_model=List[AdminMailboxResponse])
async def get_admin_mailboxes(_: TokenData = Depends(require_admin)):
    """
    Lists all connected mailboxes in the swarm across all tenants.
    """
    mailboxes = list_all_mailboxes()
    return [
        AdminMailboxResponse(
            id=m["id"],
            user_id=m["user_id"],
            email=m["email"],
            provider=m["provider"],
            is_active=m["is_active"]
        ) for m in mailboxes
    ]

@router.get("/users", response_model=List[AdminUserResponse])
async def get_admin_users(_: TokenData = Depends(require_admin)):
    """
    Lists all registered tenant accounts and their statuses.
    """
    users = get_all_users()
    return [
        AdminUserResponse(
            id=u["id"],
            email=u["email"],
            role=u["role"]
        ) for u in users
    ]

@router.get("/system/logs", response_model=List[SystemLogResponse])
async def get_admin_system_logs(_: TokenData = Depends(require_admin)):
    """
    Queries global background cluster audit logs.
    """
    logs = list_system_logs()
    return [
        SystemLogResponse(
            id=l["id"],
            timestamp=l["timestamp"],
            module=l["module"],
            event=l["event"],
            level=l["level"]
        ) for l in logs
    ]
