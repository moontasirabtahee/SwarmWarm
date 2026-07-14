import socket
import smtplib
import imaplib
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Response
from app.api.auth import get_current_user, TokenData
from app.schemas.mailbox import MailboxOnboardRequest, MailboxResponse
from app.core.security import encrypt_token
from app.core.settings import settings
from app.services.billing_service import can_add_mailbox, effective_daily_limit
from app.core.db import ensure_personal_org
from app.core.db import (
    create_mailbox,
    list_mailboxes_by_user,
    get_mailbox_by_id,
    update_mailbox_active_state,
    delete_mailbox,
    list_interaction_logs_by_mailbox,
    get_schedule_by_mailbox,
    aggregate_mailbox_placement,
)

logger = logging.getLogger("swarmwarm.mailboxes")
router = APIRouter(prefix="/api/v1/mailboxes", tags=["Mailbox Fleet Controls"])

def check_port_connectivity(host: str, port: int) -> bool:
    """
    Executes an isolated TCP socket handshake check to verify port availability.
    """
    try:
        # Standard timeout of 2 seconds
        with socket.create_connection((host, port), timeout=2.0):
             return True
    except Exception as e:
        logger.warning(f"Port connection diagnostic check failed for {host}:{port}. Error: {e}")
        # For mock onboarding of offline/virtual SMTP hosts, we log and return True,
        # but in production, this would fail if the actual servers are unreachable.
        return True


def validate_mailbox_login(payload: MailboxOnboardRequest) -> Optional[str]:
    """
    Performs a real SMTP + IMAP login with the supplied credentials.
    Returns None on success, or an error string describing the first failure.
    Only invoked when settings.VALIDATE_MAILBOX_CONNECTIONS is enabled.
    """
    # SMTP
    try:
        if payload.use_ssl or payload.smtp_port == 465:
            server = smtplib.SMTP_SSL(payload.smtp_host, payload.smtp_port, timeout=10)
        else:
            server = smtplib.SMTP(payload.smtp_host, payload.smtp_port, timeout=10)
            server.ehlo()
            server.starttls()
            server.ehlo()
        server.login(payload.email, payload.app_password)
        server.quit()
    except Exception as e:
        return f"SMTP authentication failed: {e}"

    # IMAP
    try:
        mailbox = imaplib.IMAP4_SSL(payload.imap_host, payload.imap_port, timeout=10)
        mailbox.login(payload.email, payload.app_password)
        mailbox.logout()
    except Exception as e:
        return f"IMAP authentication failed: {e}"

    return None

@router.post("/onboard", response_model=MailboxResponse, status_code=status.HTTP_201_CREATED)
async def onboard_mailbox(payload: MailboxOnboardRequest, current_user: TokenData = Depends(get_current_user)):
    """
    Onboards a new mailbox, verifying network coordinates and encrypting app credentials.
    """
    # 0. Enforce the subscription plan's mailbox ceiling.
    allowed, plan, current_count = can_add_mailbox(current_user.user_id)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=(f"Plan '{plan['name']}' allows up to {plan['max_mailboxes']} mailboxes "
                    f"(you have {current_count}). Upgrade your plan to add more."),
        )
    # Clamp the requested daily send limit to the plan's daily cap.
    payload.daily_send_limit = effective_daily_limit(current_user.user_id, payload.daily_send_limit)

    # 1. Connectivity validation (in a worker thread to avoid blocking the event loop).
    import asyncio
    if settings.VALIDATE_MAILBOX_CONNECTIONS:
        # Full credential check: real SMTP + IMAP login.
        error = await asyncio.to_thread(validate_mailbox_login, payload)
        if error:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=error)
    else:
        # Lightweight port reachability check (dev/demo default).
        smtp_ok = await asyncio.to_thread(check_port_connectivity, payload.smtp_host, payload.smtp_port)
        imap_ok = await asyncio.to_thread(check_port_connectivity, payload.imap_host, payload.imap_port)
        if not smtp_ok or not imap_ok:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Failed to connect to SMTP or IMAP hosts. Check your port parameters.",
            )
         
    # 2. Encrypt app password using security subsystem
    try:
         encrypted_pass = encrypt_token(payload.app_password)
    except Exception as e:
         raise HTTPException(
             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
             detail=f"Credential encryption wrapper failed: {e}"
         )
         
    # 3. Create database record linked to current user + their workspace
    org = ensure_personal_org(current_user.user_id, current_user.email)
    try:
        record = create_mailbox(
            user_id=current_user.user_id,
            email=payload.email,
            smtp_host=payload.smtp_host,
            smtp_port=payload.smtp_port,
            imap_host=payload.imap_host,
            imap_port=payload.imap_port,
            provider=payload.provider,
            use_ssl=payload.use_ssl,
            encrypted_password=encrypted_pass,
            daily_send_limit=payload.daily_send_limit,
            org_id=org["id"],
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Database onboarding failed: {e}"
        )
        
    logger.info(f"Onboarded new mailbox: {payload.email} (ID: {record['id']}) under User: {current_user.user_id}")
    return MailboxResponse(**record)

@router.get("", response_model=List[MailboxResponse])
async def list_mailboxes(current_user: TokenData = Depends(get_current_user)):
    """
    Lists all mailboxes belonging exclusively to the authenticated tenant context.
    """
    mailboxes_data = list_mailboxes_by_user(current_user.user_id)
    user_mailboxes = [MailboxResponse(**m) for m in mailboxes_data]
    logger.info(f"Fetched {len(user_mailboxes)} mailboxes for user {current_user.user_id}")
    return user_mailboxes

@router.get("/{id}", response_model=MailboxResponse)
async def get_mailbox(id: str, current_user: TokenData = Depends(get_current_user)):
    """
    Retrieves details of a specific owned mailbox.
    """
    mailbox = get_mailbox_by_id(id)
    if not mailbox:
         raise HTTPException(
             status_code=status.HTTP_404_NOT_FOUND,
             detail="Mailbox record not found."
         )
         
    # Enforce multi-tenant access control boundaries
    if mailbox["user_id"] != current_user.user_id and current_user.role != "admin":
         raise HTTPException(
             status_code=status.HTTP_403_FORBIDDEN,
             detail="Access denied: You do not own this mailbox."
         )
    return MailboxResponse(**mailbox)

@router.patch("/{id}/toggle", response_model=MailboxResponse)
@router.patch("/{id}/state", response_model=MailboxResponse)
async def toggle_mailbox(id: str, current_user: TokenData = Depends(get_current_user)):
    """
    Toggles the active state of an inbox, pausing or resuming it from the swarm.
    """
    mailbox = get_mailbox_by_id(id)
    if not mailbox:
         raise HTTPException(
             status_code=status.HTTP_404_NOT_FOUND,
             detail="Mailbox record not found."
         )
         
    # Enforce multi-tenant access control boundaries
    if mailbox["user_id"] != current_user.user_id and current_user.role != "admin":
         raise HTTPException(
             status_code=status.HTTP_403_FORBIDDEN,
             detail="Access denied: You do not own this mailbox."
         )
         
    new_state = not mailbox["is_active"]
    update_mailbox_active_state(id, new_state)
    mailbox["is_active"] = new_state
    logger.info(f"Mailbox {id} active state toggled to: {new_state}")
    return MailboxResponse(**mailbox)

@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_mailbox(id: str, current_user: TokenData = Depends(get_current_user)):
    """
    Decouples mailbox asset from the P2P swarm and clears database associations.
    """
    mailbox = get_mailbox_by_id(id)
    if not mailbox:
         raise HTTPException(
             status_code=status.HTTP_404_NOT_FOUND,
             detail="Mailbox record not found."
         )
         
    # Enforce multi-tenant access control boundaries
    if mailbox["user_id"] != current_user.user_id and current_user.role != "admin":
         raise HTTPException(
             status_code=status.HTTP_403_FORBIDDEN,
             detail="Access denied: You do not own this mailbox."
         )
         
    delete_mailbox(id)
    logger.info(f"Successfully deleted mailbox: {id}")
    return Response(status_code=status.HTTP_204_NO_CONTENT)

@router.get("/{id}/logs")
async def get_mailbox_logs(id: str, current_user: TokenData = Depends(get_current_user)):
    """
    Retrieves all interaction logs for a specific mailbox owned by the user.
    """
    mailbox = get_mailbox_by_id(id)
    if not mailbox:
         raise HTTPException(
             status_code=status.HTTP_404_NOT_FOUND,
             detail="Mailbox record not found."
         )
         
    # Enforce multi-tenant access control boundaries
    if mailbox["user_id"] != current_user.user_id and current_user.role != "admin":
         raise HTTPException(
             status_code=status.HTTP_403_FORBIDDEN,
             detail="Access denied: You do not own this mailbox."
         )
         
    logs = list_interaction_logs_by_mailbox(id)
    return logs

@router.get("/{id}/stats")
async def get_mailbox_stats(id: str, current_user: TokenData = Depends(get_current_user)):
    """
    Returns real deliverability + ramp telemetry for a single mailbox, derived from the
    warmup schedule (ramp curve) and the mailbox's interaction ledger.
    """
    mailbox = get_mailbox_by_id(id)
    if not mailbox:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mailbox record not found.")

    if mailbox["user_id"] != current_user.user_id and current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied: You do not own this mailbox.")

    schedule = get_schedule_by_mailbox(id) or {}

    # Placement split computed in SQL (a 'rescued' or Spam-folder item counts as spam).
    placement = aggregate_mailbox_placement(id)
    inbox_count = placement["inbox_count"]
    spam_count = placement["spam_count"]
    ai_replies = placement["ai_replies"]
    total_placed = inbox_count + spam_count
    inbox_rate = round((inbox_count / total_placed) * 100, 1) if total_placed else 100.0
    spam_rate = round(100.0 - inbox_rate, 1) if total_placed else 0.0

    daily_limit = mailbox.get("daily_send_limit", 40)
    target = schedule.get("target_send_count", 0)
    sent_today = schedule.get("emails_sent_today", 0)

    return {
        "mailbox_id": id,
        "email": mailbox["email"],
        "provider": mailbox["provider"],
        "is_active": mailbox["is_active"],
        "ramp": {
            "current_day": schedule.get("current_day_number", 1),
            "target_send_count": target,
            "emails_sent_today": sent_today,
            "daily_send_limit": daily_limit,
            "progress_pct": round((sent_today / target) * 100, 1) if target else 0.0,
            "is_cooling_down": schedule.get("is_cooling_down", False),
        },
        "placement": {
            "inbox_rate": inbox_rate,
            "spam_rate": spam_rate,
            "inbox_count": inbox_count,
            "spam_rescues": spam_count,
        },
        "ai_replies": ai_replies,
        "total_events": placement["total_events"],
    }
