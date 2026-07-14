"""
Account management — GDPR data export and account deletion.

* GET  /api/v1/account/export  — returns a portable JSON copy of the user's data.
* DELETE /api/v1/account       — permanently deletes the account (password-confirmed).
                                 FK cascades remove mailboxes, schedules, logs, tokens,
                                 subscriptions, owned orgs and memberships.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.api.auth import get_current_user, TokenData
from app.core.passwords import verify_password
from app.core.db import (
    get_user_by_id, delete_user, list_mailboxes_by_user, list_interaction_logs_by_user,
    get_subscription_by_user, list_orgs_for_user,
)

logger = logging.getLogger("swarmwarm.account")
router = APIRouter(prefix="/api/v1/account", tags=["Account"])


class DeleteAccountRequest(BaseModel):
    password: str


@router.get("/export")
async def export_account(current_user: TokenData = Depends(get_current_user)):
    """Data-portability export of everything tied to the authenticated account."""
    user = get_user_by_id(current_user.user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    mailboxes = list_mailboxes_by_user(current_user.user_id)
    for m in mailboxes:
        m.pop("encrypted_password", None)  # never export secrets

    return {
        "profile": {
            "id": user["id"],
            "email": user["email"],
            "full_name": user.get("full_name"),
            "role": user["role"],
            "is_verified": bool(user.get("is_verified")),
            "created_at": user.get("created_at"),
        },
        "subscription": get_subscription_by_user(current_user.user_id),
        "organizations": list_orgs_for_user(current_user.user_id),
        "mailboxes": mailboxes,
        "interaction_logs": list_interaction_logs_by_user(current_user.user_id),
    }


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(payload: DeleteAccountRequest, current_user: TokenData = Depends(get_current_user)):
    """Permanently delete the account after confirming the password."""
    user = get_user_by_id(current_user.user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    if not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Password confirmation failed.")

    delete_user(current_user.user_id)
    logger.info("Account permanently deleted: %s (%s)", user["email"], user["id"])
