"""
Data-access helpers for SwarmWarm.

Backed by a single SQLAlchemy engine (`app.core.database.engine`) so the exact same
code runs on SQLite (dev) and PostgreSQL (prod). Public helper names, signatures and
return shapes are unchanged from the original SQLite implementation, so API routers
and workers do not need to change.
"""
import uuid
from typing import Optional, List

from sqlalchemy import select, insert, update, delete, func, case, and_, or_

from app.core.settings import settings
from app.core.database import engine, create_schema, sync_missing_columns
from app.core.models import (
    now_iso,
    users, mailboxes, warmup_schedules, interaction_logs, system_logs,
    refresh_tokens, password_resets, email_verifications,
    plans, subscriptions,
    organizations, org_members, invitations,
)

# Default billing tiers seeded on startup (idempotent).
DEFAULT_PLANS = [
    # id,   name,   price_cents, max_mailboxes, daily_send_cap
    ("free",  "Free",     0,     2,   40),
    ("pro",   "Pro",   4900,    10,  100),
    ("scale", "Scale", 14900,   50,  250),
]

# Demo seed password (documented in README). The hash is recomputed at seed time
# (bcrypt) so the demo credentials are always valid.
SEED_PASSWORD = "SwarmWarm2026!"

# Length (in days) of the deliverability ramp curve before a mailbox reaches its ceiling.
RAMP_CURVE_DAYS = 30
RAMP_START_VOLUME = 2


def _new_id(prefix: str) -> str:
    """Generates a collision-free identifier (uuid-based) for a table row."""
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def ramp_target_for_day(day_number: int, daily_send_limit: int) -> int:
    """
    Computes the target outbound volume for a given ramp day.
    Linearly scales from RAMP_START_VOLUME up to daily_send_limit across RAMP_CURVE_DAYS.
    """
    if day_number >= RAMP_CURVE_DAYS:
        return daily_send_limit
    span = max(1, daily_send_limit - RAMP_START_VOLUME)
    step = span / (RAMP_CURVE_DAYS - 1)
    return min(daily_send_limit, int(round(RAMP_START_VOLUME + (day_number - 1) * step)))


def _insert_schedule(conn, mailbox_id: str, day_number: int = 1, emails_sent_today: int = 0,
                     daily_send_limit: int = 40, is_cooling_down: bool = False):
    target = ramp_target_for_day(day_number, daily_send_limit)
    conn.execute(insert(warmup_schedules).values(
        id=_new_id("sched"),
        mailbox_id=mailbox_id,
        current_day_number=day_number,
        target_send_count=target,
        emails_sent_today=emails_sent_today,
        is_cooling_down=is_cooling_down,
        last_processed_at=now_iso(),
        updated_at=now_iso(),
    ))


def init_db():
    """
    Creates tables, applies lightweight column migrations, and seeds demo data if empty.
    """
    # On SQLite (dev/test) we build + patch the schema in-process. On PostgreSQL the
    # schema is owned by Alembic (`alembic upgrade head`), so we don't create_all or
    # inspect every table on each boot — we go straight to idempotent seeding.
    if settings.is_sqlite:
        create_schema()
        sync_missing_columns()

    with engine.begin() as conn:
        _ensure_default_plans(conn)

        user_count = conn.execute(select(func.count()).select_from(users)).scalar_one()
        if user_count == 0:
            _seed_demo_data(conn)

        # Backfill a warmup schedule for any mailbox that is missing one.
        existing = {r[0] for r in conn.execute(select(warmup_schedules.c.mailbox_id)).fetchall()}
        for mid in conn.execute(select(mailboxes.c.id)).fetchall():
            if mid[0] not in existing:
                _insert_schedule(conn, mid[0], day_number=1, emails_sent_today=0)

        # Ensure every user has a subscription (default: free tier).
        subbed = {r[0] for r in conn.execute(select(subscriptions.c.user_id)).fetchall()}
        for uid in conn.execute(select(users.c.id)).fetchall():
            if uid[0] not in subbed:
                conn.execute(insert(subscriptions).values(
                    id=_new_id("sub"), user_id=uid[0], plan_id="free", status="active",
                    created_at=now_iso(), updated_at=now_iso(),
                ))

        # Snapshot users needing a personal workspace + mailboxes needing an org stamp,
        # then apply outside this transaction (helpers manage their own connections).
        owned_orgs = {r[0] for r in conn.execute(select(organizations.c.owner_user_id)).fetchall()}
        users_needing_org = [(r[0], r[1]) for r in
                             conn.execute(select(users.c.id, users.c.email)).fetchall()
                             if r[0] not in owned_orgs]

    for uid, email in users_needing_org:
        org = ensure_personal_org(uid, email)
        # Stamp any of this owner's mailboxes that predate org scoping.
        with engine.begin() as conn:
            conn.execute(update(mailboxes)
                         .where((mailboxes.c.user_id == uid) & (mailboxes.c.org_id.is_(None)))
                         .values(org_id=org["id"]))


def _ensure_default_plans(conn):
    """Idempotently upsert the default billing tiers."""
    existing = {r[0] for r in conn.execute(select(plans.c.id)).fetchall()}
    for pid, name, price, max_mb, cap in DEFAULT_PLANS:
        if pid not in existing:
            conn.execute(insert(plans).values(
                id=pid, name=name, price_cents=price, max_mailboxes=max_mb,
                daily_send_cap=cap, is_active=True,
            ))


def _seed_demo_data(conn):
    """Inserts deterministic demo data with a known, documented password."""
    from app.core.passwords import hash_password
    default_pwd_hash = hash_password(SEED_PASSWORD)

    seed_users = [
        ("user_admin", "ieee.dobby1998@gmail.com", "admin"),
        ("user_qoarc", "abtahee@qoarc.com", "user"),
        ("user_bmafia", "m.abtahee@brownmafia.com", "user"),
    ]
    for uid, email, role in seed_users:
        conn.execute(insert(users).values(
            id=uid, email=email, password_hash=default_pwd_hash, role=role,
            is_verified=True, created_at=now_iso(),
        ))

    seed_mailboxes = [
        ("mailbox_admin_google", "user_admin", "ieee.dobby1998@gmail.com", "smtp.gmail.com", 465,
         "imap.gmail.com", 993, "PTT8XA-KBmrFyBphxcUTX8R1yB4zlZs0H3qSeG8301NLBPdIDOTkgv06TkBXuXs=", "google", True, 40, 22),
        ("mailbox_qoarc_google", "user_qoarc", "abtahee@qoarc.com", "smtp.gmail.com", 465,
         "imap.gmail.com", 993, "4jRTREI1DyqWaIt1SaI7aF2A_MELB1zDvSFyFOJwQBVpCfeOT1rRSV-mPpiWgpcMUbkHcV8g-0fRZGMmBvLL", "google", True, 40, 14),
        ("mailbox_bmafia_microsoft", "user_bmafia", "m.abtahee@brownmafia.com", "smtp.office365.com", 587,
         "outlook.office365.com", 993, "GS4Cqdt1Jnc3TGrTpi_fKuPFQB73mlp0CjWehQW3-7jqmAli-CfyS1sFb1uyg_J_zAldJ9EjUxPcfKpxP1GY", "microsoft", False, 50, 8),
    ]
    for (mid, uid, email, sh, sp, ih, ip, enc, prov, ssl, limit, day) in seed_mailboxes:
        conn.execute(insert(mailboxes).values(
            id=mid, user_id=uid, email=email, smtp_host=sh, smtp_port=sp,
            imap_host=ih, imap_port=ip, encrypted_password=enc, provider=prov,
            use_ssl=ssl, daily_send_limit=limit, is_active=True, created_at=now_iso(),
        ))
        target = ramp_target_for_day(day, limit)
        sent_today = max(0, target - 3)
        _insert_schedule(conn, mid, day_number=day, emails_sent_today=sent_today, daily_send_limit=limit)

    seed_logs = [
        ("log_1", "user_qoarc", "mailbox_qoarc_google", "m.abtahee@brownmafia.com", "Warmup Sync Request", "sent", "INBOX", True, "2026-07-12T10:00:00Z"),
        ("log_2", "user_qoarc", "mailbox_qoarc_google", "node01@mabsj.com", "Warmup Sync Request", "sent", "INBOX", True, "2026-07-12T12:00:00Z"),
        ("log_3", "user_qoarc", "mailbox_qoarc_google", "outreach@startup.net", "SwarmWarm Rescue", "rescued", "Spam", False, "2026-07-12T14:00:00Z"),
        ("log_4", "user_qoarc", "mailbox_qoarc_google", "outreach@startup.net", "Warmup Sync Request", "sent", "INBOX", False, "2026-07-12T16:00:00Z"),
        ("log_5", "user_bmafia", "mailbox_bmafia_microsoft", "abtahee@qoarc.com", "Warmup Sync Request", "sent", "INBOX", True, "2026-07-12T11:00:00Z"),
    ]
    for (lid, uid, mid, rcpt, subj, action, folder, ai, created) in seed_logs:
        conn.execute(insert(interaction_logs).values(
            id=lid, user_id=uid, mailbox_id=mid, recipient_email=rcpt, subject=subj,
            action=action, folder=folder, ai_replied=ai, created_at=created,
        ))

    seed_syslogs = [
        ("syslog_1", "2026-07-12 20:38:12", "CELERY_BEAT", "Nightly P2P bipartite graph mapping complete.", "INFO"),
        ("syslog_2", "2026-07-12 20:39:01", "REDIS_BROKER", "Enqueued 42 task items into FIFO channel buffer.", "INFO"),
        ("syslog_3", "2026-07-12 20:41:14", "LOCAL_AI_NODE", "Gemma 4B compiled context tokens. (42 t/s)", "INFO"),
        ("syslog_4", "2026-07-12 20:45:22", "SMTP_WORKER_02", "Connection block jitter offset applied: 47s.", "INFO"),
        ("syslog_5", "2026-07-12 20:50:05", "IMAP_WORKER_01", "[RESCUE] Account abtahee@qoarc.com flag fix complete.", "INFO"),
    ]
    for (sid, ts, module, event, level) in seed_syslogs:
        conn.execute(insert(system_logs).values(
            id=sid, timestamp=ts, module=module, event=event, level=level,
        ))


# --- HELPER FUNCTIONS FOR USERS ---

def get_user_by_email(email: str) -> Optional[dict]:
    # Emails are always stored lowercased (create_user + seed), so an exact match on
    # the lowercased input uses the unique email index instead of a full scan.
    with engine.connect() as conn:
        row = conn.execute(
            select(users).where(users.c.email == email.lower())
        ).mappings().first()
    return dict(row) if row else None


def get_user_by_id(user_id: str) -> Optional[dict]:
    with engine.connect() as conn:
        row = conn.execute(select(users).where(users.c.id == user_id)).mappings().first()
    return dict(row) if row else None


def create_user(email: str, password_hash: str, role: str = "user",
                is_verified: bool = False, full_name: Optional[str] = None) -> dict:
    user_id = _new_id("user")
    with engine.begin() as conn:
        conn.execute(insert(users).values(
            id=user_id, email=email.lower(), password_hash=password_hash, role=role,
            is_verified=is_verified, full_name=full_name, created_at=now_iso(),
        ))
        row = conn.execute(select(users).where(users.c.id == user_id)).mappings().first()
    return dict(row)


def update_user_password(user_id: str, password_hash: str):
    with engine.begin() as conn:
        conn.execute(update(users).where(users.c.id == user_id).values(password_hash=password_hash))


def set_user_verified(user_id: str, verified: bool = True):
    with engine.begin() as conn:
        conn.execute(update(users).where(users.c.id == user_id).values(is_verified=verified))


def delete_user(user_id: str):
    with engine.begin() as conn:
        conn.execute(delete(users).where(users.c.id == user_id))


def get_user_count() -> int:
    with engine.connect() as conn:
        return conn.execute(select(func.count()).select_from(users)).scalar_one()


def get_all_users() -> List[dict]:
    with engine.connect() as conn:
        rows = conn.execute(select(users)).mappings().all()
    return [dict(r) for r in rows]


# --- HELPER FUNCTIONS FOR MAILBOXES ---

def _hydrate_mailbox(row) -> dict:
    d = dict(row)
    d["is_active"] = bool(d["is_active"])
    d["use_ssl"] = bool(d["use_ssl"])
    if d.get("daily_send_limit") is None:
        d["daily_send_limit"] = 40
    return d


def get_mailbox_by_id(mailbox_id: str) -> Optional[dict]:
    with engine.connect() as conn:
        row = conn.execute(select(mailboxes).where(mailboxes.c.id == mailbox_id)).mappings().first()
    return _hydrate_mailbox(row) if row else None


def create_mailbox(user_id: str, email: str, smtp_host: str, smtp_port: int, imap_host: str, imap_port: int,
                   provider: str, use_ssl: bool, encrypted_password: str, daily_send_limit: int = 40,
                   org_id: Optional[str] = None) -> dict:
    mailbox_id = _new_id("mailbox")
    with engine.begin() as conn:
        conn.execute(insert(mailboxes).values(
            id=mailbox_id, user_id=user_id, org_id=org_id, email=email,
            smtp_host=smtp_host, smtp_port=smtp_port, imap_host=imap_host, imap_port=imap_port,
            encrypted_password=encrypted_password, provider=provider, use_ssl=use_ssl,
            daily_send_limit=daily_send_limit, is_active=True, created_at=now_iso(),
        ))
        # Every onboarded mailbox starts a fresh warmup schedule on day 1.
        _insert_schedule(conn, mailbox_id, day_number=1, emails_sent_today=0, daily_send_limit=daily_send_limit)
        row = conn.execute(select(mailboxes).where(mailboxes.c.id == mailbox_id)).mappings().first()
    return _hydrate_mailbox(row)


def get_mailbox_count() -> int:
    with engine.connect() as conn:
        return conn.execute(select(func.count()).select_from(mailboxes)).scalar_one()


def count_mailboxes_by_user(user_id: str) -> int:
    with engine.connect() as conn:
        return conn.execute(
            select(func.count()).select_from(mailboxes).where(mailboxes.c.user_id == user_id)
        ).scalar_one()


def list_mailboxes_by_user(user_id: str) -> List[dict]:
    with engine.connect() as conn:
        rows = conn.execute(select(mailboxes).where(mailboxes.c.user_id == user_id)).mappings().all()
    return [_hydrate_mailbox(r) for r in rows]


def list_all_mailboxes() -> List[dict]:
    with engine.connect() as conn:
        rows = conn.execute(select(mailboxes)).mappings().all()
    return [_hydrate_mailbox(r) for r in rows]


def update_mailbox_active_state(mailbox_id: str, is_active: bool):
    with engine.begin() as conn:
        conn.execute(update(mailboxes).where(mailboxes.c.id == mailbox_id).values(is_active=is_active))


def delete_mailbox(mailbox_id: str):
    with engine.begin() as conn:
        conn.execute(delete(mailboxes).where(mailboxes.c.id == mailbox_id))


# --- HELPER FUNCTIONS FOR WARMUP SCHEDULES ---

def get_schedule_by_mailbox(mailbox_id: str) -> Optional[dict]:
    with engine.connect() as conn:
        row = conn.execute(
            select(warmup_schedules).where(warmup_schedules.c.mailbox_id == mailbox_id)
        ).mappings().first()
    if not row:
        return None
    d = dict(row)
    d["is_cooling_down"] = bool(d["is_cooling_down"])
    return d


def increment_emails_sent(mailbox_id: str, amount: int = 1):
    with engine.begin() as conn:
        conn.execute(
            update(warmup_schedules)
            .where(warmup_schedules.c.mailbox_id == mailbox_id)
            .values(
                emails_sent_today=warmup_schedules.c.emails_sent_today + amount,
                updated_at=now_iso(),
            )
        )


def advance_schedule_day(mailbox_id: str):
    """Advances a mailbox to the next ramp day and resets the daily counter (nightly scheduler)."""
    with engine.begin() as conn:
        row = conn.execute(
            select(warmup_schedules.c.current_day_number, mailboxes.c.daily_send_limit)
            .select_from(warmup_schedules.join(mailboxes, mailboxes.c.id == warmup_schedules.c.mailbox_id))
            .where(warmup_schedules.c.mailbox_id == mailbox_id)
        ).mappings().first()
        if row:
            next_day = row["current_day_number"] + 1
            limit = row["daily_send_limit"] or 40
            target = ramp_target_for_day(next_day, limit)
            conn.execute(
                update(warmup_schedules)
                .where(warmup_schedules.c.mailbox_id == mailbox_id)
                .values(
                    current_day_number=next_day,
                    target_send_count=target,
                    emails_sent_today=0,
                    last_processed_at=now_iso(),
                    updated_at=now_iso(),
                )
            )


# --- HELPER FUNCTIONS FOR INTERACTION LOGS ---

def create_interaction_log(user_id: str, mailbox_id: str, action: str, folder: str, ai_replied: bool,
                           subject: Optional[str] = None, recipient_email: Optional[str] = "",
                           error_message: Optional[str] = None) -> dict:
    log_id = _new_id("log")
    created = now_iso()
    with engine.begin() as conn:
        conn.execute(insert(interaction_logs).values(
            id=log_id, user_id=user_id, mailbox_id=mailbox_id, recipient_email=recipient_email,
            subject=subject, action=action, folder=folder, ai_replied=ai_replied,
            error_message=error_message, created_at=created,
        ))
    # Return shape matches a hydrated row without a second round-trip.
    return {
        "id": log_id, "user_id": user_id, "mailbox_id": mailbox_id,
        "recipient_email": recipient_email, "subject": subject, "action": action,
        "folder": folder, "ai_replied": bool(ai_replied), "error_message": error_message,
        "created_at": created,
    }


def _logs_to_dicts(rows) -> List[dict]:
    out = []
    for r in rows:
        d = dict(r)
        d["ai_replied"] = bool(d["ai_replied"])
        out.append(d)
    return out


def list_interaction_logs_by_user(user_id: str) -> List[dict]:
    with engine.connect() as conn:
        rows = conn.execute(
            select(interaction_logs).where(interaction_logs.c.user_id == user_id)
            .order_by(interaction_logs.c.created_at.desc())
        ).mappings().all()
    return _logs_to_dicts(rows)


def list_interaction_logs_by_mailbox(mailbox_id: str) -> List[dict]:
    with engine.connect() as conn:
        rows = conn.execute(
            select(interaction_logs).where(interaction_logs.c.mailbox_id == mailbox_id)
            .order_by(interaction_logs.c.created_at.desc())
        ).mappings().all()
    return _logs_to_dicts(rows)


def list_all_interaction_logs() -> List[dict]:
    with engine.connect() as conn:
        rows = conn.execute(
            select(interaction_logs).order_by(interaction_logs.c.created_at.desc()).limit(100)
        ).mappings().all()
    return _logs_to_dicts(rows)


# --- INTERACTION LOG AGGREGATION (SQL-side, avoids pulling rows into Python) ---

_IL = interaction_logs.c
# Case expressions mirror the previous Python counting logic exactly.
_c_sent = case((_IL.action == "sent", 1), else_=0)
_c_inbox_sent = case(
    (and_(_IL.action == "sent", func.upper(func.coalesce(_IL.folder, "INBOX")) == "INBOX"), 1),
    else_=0,
)
_c_rescued = case((_IL.action == "rescued", 1), else_=0)
_c_spam_folder = case(
    (or_(_IL.action == "rescued", func.upper(func.coalesce(_IL.folder, "")) == "SPAM"), 1),
    else_=0,
)
_c_ai = case((_IL.ai_replied == True, 1), else_=0)  # noqa: E712


def _overview_metrics(where_clause) -> dict:
    """
    SQL conditional aggregation matching the analytics/stream Python logic:
    a 'rescued' item counts as an inbox placement.
    """
    stmt = select(
        func.coalesce(func.sum(_c_sent), 0),
        func.coalesce(func.sum(_c_inbox_sent), 0),
        func.coalesce(func.sum(_c_rescued), 0),
        func.coalesce(func.sum(_c_ai), 0),
    ).select_from(interaction_logs)
    if where_clause is not None:
        stmt = stmt.where(where_clause)
    with engine.connect() as conn:
        total_sent, inbox_from_sent, spam_rescues, ai_replies = conn.execute(stmt).one()
    total_sent, inbox_from_sent = int(total_sent), int(inbox_from_sent)
    spam_rescues, ai_replies = int(spam_rescues), int(ai_replies)
    return {
        "total_sent": total_sent,
        "spam_rescues": spam_rescues,
        "ai_replies": ai_replies,
        "inbox_placements": inbox_from_sent + spam_rescues,
    }


def aggregate_metrics_by_user(user_id: str) -> dict:
    return _overview_metrics(_IL.user_id == user_id)


def count_interaction_logs_by_user(user_id: str) -> int:
    with engine.connect() as conn:
        return conn.execute(
            select(func.count()).select_from(interaction_logs).where(_IL.user_id == user_id)
        ).scalar_one()


def get_latest_interaction_log_by_user(user_id: str) -> Optional[dict]:
    with engine.connect() as conn:
        row = conn.execute(
            select(interaction_logs).where(_IL.user_id == user_id)
            .order_by(_IL.created_at.desc()).limit(1)
        ).mappings().first()
    if not row:
        return None
    d = dict(row)
    d["ai_replied"] = bool(d["ai_replied"])
    return d


def aggregate_mailbox_placement(mailbox_id: str) -> dict:
    """Per-mailbox placement split (a 'rescued' OR Spam-folder item counts as spam)."""
    stmt = select(
        func.coalesce(func.sum(_c_inbox_sent), 0),
        func.coalesce(func.sum(_c_spam_folder), 0),
        func.coalesce(func.sum(_c_ai), 0),
        func.count(),
    ).select_from(interaction_logs).where(_IL.mailbox_id == mailbox_id)
    with engine.connect() as conn:
        inbox_count, spam_count, ai_replies, total_events = conn.execute(stmt).one()
    return {
        "inbox_count": int(inbox_count),
        "spam_count": int(spam_count),
        "ai_replies": int(ai_replies),
        "total_events": int(total_events),
    }


# --- HELPER FUNCTIONS FOR SYSTEM LOGS ---

def create_system_log(module: str, event: str, level: str = "INFO") -> dict:
    from datetime import datetime, timezone
    log_id = _new_id("syslog")
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    with engine.begin() as conn:
        conn.execute(insert(system_logs).values(
            id=log_id, timestamp=timestamp, module=module, event=event, level=level,
        ))
    return {"id": log_id, "timestamp": timestamp, "module": module, "event": event, "level": level}


def list_system_logs() -> List[dict]:
    with engine.connect() as conn:
        rows = conn.execute(
            select(system_logs).order_by(system_logs.c.timestamp.desc()).limit(50)
        ).mappings().all()
    return [dict(r) for r in rows]


# --- REFRESH TOKENS ---

def create_refresh_token(user_id: str, token_hash: str, expires_at: str) -> str:
    rid = _new_id("rtok")
    with engine.begin() as conn:
        conn.execute(insert(refresh_tokens).values(
            id=rid, user_id=user_id, token_hash=token_hash, expires_at=expires_at,
            revoked=False, created_at=now_iso(),
        ))
    return rid


def get_refresh_token(token_hash: str) -> Optional[dict]:
    with engine.connect() as conn:
        row = conn.execute(
            select(refresh_tokens).where(refresh_tokens.c.token_hash == token_hash)
        ).mappings().first()
    if not row:
        return None
    d = dict(row)
    d["revoked"] = bool(d["revoked"])
    return d


def revoke_refresh_token(token_hash: str):
    with engine.begin() as conn:
        conn.execute(
            update(refresh_tokens).where(refresh_tokens.c.token_hash == token_hash).values(revoked=True)
        )


def revoke_all_refresh_tokens(user_id: str):
    with engine.begin() as conn:
        conn.execute(
            update(refresh_tokens).where(refresh_tokens.c.user_id == user_id).values(revoked=True)
        )


# --- PASSWORD RESETS ---

def create_password_reset(user_id: str, token_hash: str, expires_at: str) -> str:
    pid = _new_id("prst")
    with engine.begin() as conn:
        conn.execute(insert(password_resets).values(
            id=pid, user_id=user_id, token_hash=token_hash, expires_at=expires_at,
            used=False, created_at=now_iso(),
        ))
    return pid


def get_password_reset(token_hash: str) -> Optional[dict]:
    with engine.connect() as conn:
        row = conn.execute(
            select(password_resets).where(password_resets.c.token_hash == token_hash)
        ).mappings().first()
    if not row:
        return None
    d = dict(row)
    d["used"] = bool(d["used"])
    return d


def mark_password_reset_used(token_hash: str):
    with engine.begin() as conn:
        conn.execute(
            update(password_resets).where(password_resets.c.token_hash == token_hash).values(used=True)
        )


# --- EMAIL VERIFICATIONS ---

def create_email_verification(user_id: str, token_hash: str, expires_at: str) -> str:
    eid = _new_id("evrf")
    with engine.begin() as conn:
        conn.execute(insert(email_verifications).values(
            id=eid, user_id=user_id, token_hash=token_hash, expires_at=expires_at,
            used=False, created_at=now_iso(),
        ))
    return eid


def get_email_verification(token_hash: str) -> Optional[dict]:
    with engine.connect() as conn:
        row = conn.execute(
            select(email_verifications).where(email_verifications.c.token_hash == token_hash)
        ).mappings().first()
    if not row:
        return None
    d = dict(row)
    d["used"] = bool(d["used"])
    return d


def mark_email_verification_used(token_hash: str):
    with engine.begin() as conn:
        conn.execute(
            update(email_verifications).where(email_verifications.c.token_hash == token_hash).values(used=True)
        )


# --- BILLING: PLANS + SUBSCRIPTIONS ---

def list_plans() -> List[dict]:
    with engine.connect() as conn:
        rows = conn.execute(
            select(plans).where(plans.c.is_active == True).order_by(plans.c.price_cents)  # noqa: E712
        ).mappings().all()
    return [dict(r) for r in rows]


def get_plan(plan_id: str) -> Optional[dict]:
    with engine.connect() as conn:
        row = conn.execute(select(plans).where(plans.c.id == plan_id)).mappings().first()
    return dict(row) if row else None


def get_subscription_by_user(user_id: str) -> Optional[dict]:
    with engine.connect() as conn:
        row = conn.execute(
            select(subscriptions).where(subscriptions.c.user_id == user_id)
        ).mappings().first()
    return dict(row) if row else None


def ensure_subscription(user_id: str, plan_id: str = "free") -> dict:
    """Return the user's subscription, creating a default one if absent."""
    existing = get_subscription_by_user(user_id)
    if existing:
        return existing
    with engine.begin() as conn:
        conn.execute(insert(subscriptions).values(
            id=_new_id("sub"), user_id=user_id, plan_id=plan_id, status="active",
            created_at=now_iso(), updated_at=now_iso(),
        ))
    return get_subscription_by_user(user_id)


def set_subscription_plan(user_id: str, plan_id: str, status: str = "active",
                          stripe_customer_id: Optional[str] = None,
                          stripe_subscription_id: Optional[str] = None,
                          current_period_end: Optional[str] = None):
    """Upsert a user's subscription to the given plan (used by billing + Stripe webhooks)."""
    ensure_subscription(user_id)
    values = {"plan_id": plan_id, "status": status, "updated_at": now_iso()}
    if stripe_customer_id is not None:
        values["stripe_customer_id"] = stripe_customer_id
    if stripe_subscription_id is not None:
        values["stripe_subscription_id"] = stripe_subscription_id
    if current_period_end is not None:
        values["current_period_end"] = current_period_end
    with engine.begin() as conn:
        conn.execute(update(subscriptions).where(subscriptions.c.user_id == user_id).values(**values))


def get_user_by_stripe_customer(customer_id: str) -> Optional[dict]:
    with engine.connect() as conn:
        row = conn.execute(
            select(subscriptions).where(subscriptions.c.stripe_customer_id == customer_id)
        ).mappings().first()
    return dict(row) if row else None


# --- ORGANIZATIONS / TEAMS ---

def create_organization(name: str, owner_user_id: str) -> dict:
    org_id = _new_id("org")
    with engine.begin() as conn:
        conn.execute(insert(organizations).values(
            id=org_id, name=name, owner_user_id=owner_user_id, created_at=now_iso(),
        ))
        conn.execute(insert(org_members).values(
            id=_new_id("mbr"), org_id=org_id, user_id=owner_user_id, role="owner", created_at=now_iso(),
        ))
        row = conn.execute(select(organizations).where(organizations.c.id == org_id)).mappings().first()
    return dict(row)


def get_organization(org_id: str) -> Optional[dict]:
    with engine.connect() as conn:
        row = conn.execute(select(organizations).where(organizations.c.id == org_id)).mappings().first()
    return dict(row) if row else None


def list_orgs_for_user(user_id: str) -> List[dict]:
    with engine.connect() as conn:
        rows = conn.execute(
            select(organizations, org_members.c.role)
            .select_from(organizations.join(org_members, org_members.c.org_id == organizations.c.id))
            .where(org_members.c.user_id == user_id)
        ).mappings().all()
    return [dict(r) for r in rows]


def get_org_membership(org_id: str, user_id: str) -> Optional[dict]:
    with engine.connect() as conn:
        row = conn.execute(
            select(org_members).where(
                (org_members.c.org_id == org_id) & (org_members.c.user_id == user_id)
            )
        ).mappings().first()
    return dict(row) if row else None


def add_org_member(org_id: str, user_id: str, role: str = "member") -> Optional[dict]:
    existing = get_org_membership(org_id, user_id)
    if existing:
        return existing
    with engine.begin() as conn:
        conn.execute(insert(org_members).values(
            id=_new_id("mbr"), org_id=org_id, user_id=user_id, role=role, created_at=now_iso(),
        ))
    return get_org_membership(org_id, user_id)


def list_org_members(org_id: str) -> List[dict]:
    with engine.connect() as conn:
        rows = conn.execute(
            select(org_members.c.role, org_members.c.created_at, users.c.id, users.c.email, users.c.full_name)
            .select_from(org_members.join(users, users.c.id == org_members.c.user_id))
            .where(org_members.c.org_id == org_id)
        ).mappings().all()
    return [dict(r) for r in rows]


def remove_org_member(org_id: str, user_id: str):
    with engine.begin() as conn:
        conn.execute(delete(org_members).where(
            (org_members.c.org_id == org_id) & (org_members.c.user_id == user_id)
        ))


def get_personal_org_for_user(user_id: str) -> Optional[dict]:
    """The org a user owns (their personal/default workspace)."""
    with engine.connect() as conn:
        row = conn.execute(
            select(organizations).where(organizations.c.owner_user_id == user_id)
            .order_by(organizations.c.created_at).limit(1)
        ).mappings().first()
    return dict(row) if row else None


def ensure_personal_org(user_id: str, email: str) -> dict:
    """Guarantee the user has a personal workspace; create one if missing."""
    existing = get_personal_org_for_user(user_id)
    if existing:
        return existing
    return create_organization(name=f"{email}'s Workspace", owner_user_id=user_id)


def list_mailboxes_by_org(org_id: str) -> List[dict]:
    with engine.connect() as conn:
        rows = conn.execute(select(mailboxes).where(mailboxes.c.org_id == org_id)).mappings().all()
    return [_hydrate_mailbox(r) for r in rows]


# --- INVITATIONS ---

def create_invitation(org_id: str, email: str, role: str, token_hash: str,
                      expires_at: str, invited_by: str) -> str:
    inv_id = _new_id("inv")
    with engine.begin() as conn:
        conn.execute(insert(invitations).values(
            id=inv_id, org_id=org_id, email=email.lower(), role=role, token_hash=token_hash,
            status="pending", expires_at=expires_at, invited_by=invited_by, created_at=now_iso(),
        ))
    return inv_id


def get_invitation(token_hash: str) -> Optional[dict]:
    with engine.connect() as conn:
        row = conn.execute(
            select(invitations).where(invitations.c.token_hash == token_hash)
        ).mappings().first()
    return dict(row) if row else None


def list_invitations_for_org(org_id: str) -> List[dict]:
    with engine.connect() as conn:
        rows = conn.execute(
            select(invitations).where(invitations.c.org_id == org_id)
            .order_by(invitations.c.created_at.desc())
        ).mappings().all()
    return [dict(r) for r in rows]


def set_invitation_status(token_hash: str, status_value: str):
    with engine.begin() as conn:
        conn.execute(
            update(invitations).where(invitations.c.token_hash == token_hash).values(status=status_value)
        )


# Auto-initialize database on module import (dev convenience for SQLite).
# Placed at the end so every helper referenced by init_db() is already defined.
init_db()
