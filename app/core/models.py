"""
SQLAlchemy Core schema definitions (single source of truth for the DB schema).

Used both by the dev bootstrap (`metadata.create_all`) and by Alembic migrations
(`target_metadata = metadata`). Tables are dialect-neutral so the same schema builds
on SQLite (dev) and PostgreSQL (prod).

Timestamps are stored as ISO-8601 strings (TEXT) to keep behaviour identical across
dialects and consistent with how the workers write timestamps.
"""
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
)

metadata = MetaData()


def now_iso() -> str:
    """UTC timestamp as an ISO-8601 string with a trailing Z."""
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat() + "Z"


# --------------------------------------------------------------------------- #
# Core tenant tables
# --------------------------------------------------------------------------- #
users = Table(
    "users", metadata,
    Column("id", String, primary_key=True),
    Column("email", String, nullable=False, unique=True),
    Column("password_hash", String, nullable=False),
    Column("role", String, nullable=False, default="user"),
    Column("full_name", String, nullable=True),
    Column("is_verified", Boolean, nullable=False, default=False),
    Column("created_at", String, default=now_iso),
)

organizations = Table(
    "organizations", metadata,
    Column("id", String, primary_key=True),
    Column("name", String, nullable=False),
    Column("owner_user_id", String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
    Column("created_at", String, default=now_iso),
)

org_members = Table(
    "org_members", metadata,
    Column("id", String, primary_key=True),
    Column("org_id", String, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
    Column("user_id", String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
    Column("role", String, nullable=False, default="member"),  # owner | admin | member
    Column("created_at", String, default=now_iso),
    UniqueConstraint("org_id", "user_id", name="uq_org_member"),
)

invitations = Table(
    "invitations", metadata,
    Column("id", String, primary_key=True),
    Column("org_id", String, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
    Column("email", String, nullable=False),
    Column("role", String, nullable=False, default="member"),
    Column("token_hash", String, nullable=False),
    Column("status", String, nullable=False, default="pending"),  # pending | accepted | revoked
    Column("expires_at", String, nullable=False),
    Column("invited_by", String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
    Column("created_at", String, default=now_iso),
)

mailboxes = Table(
    "mailboxes", metadata,
    Column("id", String, primary_key=True),
    Column("user_id", String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
    Column("org_id", String, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True),
    Column("email", String, nullable=False, unique=True),
    Column("smtp_host", String, nullable=False),
    Column("smtp_port", Integer, nullable=False),
    Column("imap_host", String, nullable=False),
    Column("imap_port", Integer, nullable=False),
    Column("encrypted_password", Text, nullable=False),
    Column("provider", String, nullable=False),
    Column("use_ssl", Boolean, nullable=False, default=True),
    Column("daily_send_limit", Integer, default=40),
    Column("is_active", Boolean, nullable=False, default=True),
    Column("created_at", String, default=now_iso),
)

warmup_schedules = Table(
    "warmup_schedules", metadata,
    Column("id", String, primary_key=True),
    Column("mailbox_id", String, ForeignKey("mailboxes.id", ondelete="CASCADE"), nullable=False, unique=True),
    Column("current_day_number", Integer, default=1),
    Column("target_send_count", Integer, default=2),
    Column("emails_sent_today", Integer, default=0),
    Column("is_cooling_down", Boolean, default=False),
    Column("last_processed_at", String, nullable=True),
    Column("updated_at", String, default=now_iso),
)

interaction_logs = Table(
    "interaction_logs", metadata,
    Column("id", String, primary_key=True),
    Column("user_id", String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
    Column("mailbox_id", String, ForeignKey("mailboxes.id", ondelete="SET NULL"), nullable=True),
    Column("recipient_email", String, nullable=False),
    Column("subject", String, nullable=True),
    Column("action", String, nullable=False),
    Column("folder", String, default="INBOX"),
    Column("ai_replied", Boolean, default=False),
    Column("error_message", String, nullable=True),
    Column("created_at", String, default=now_iso),
)

system_logs = Table(
    "system_logs", metadata,
    Column("id", String, primary_key=True),
    Column("timestamp", String, nullable=False),
    Column("module", String, nullable=False),
    Column("event", String, nullable=False),
    Column("level", String, nullable=False, default="INFO"),
)


# --------------------------------------------------------------------------- #
# Auth support tables
# --------------------------------------------------------------------------- #
refresh_tokens = Table(
    "refresh_tokens", metadata,
    Column("id", String, primary_key=True),
    Column("user_id", String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
    Column("token_hash", String, nullable=False, unique=True),
    Column("expires_at", String, nullable=False),
    Column("revoked", Boolean, nullable=False, default=False),
    Column("created_at", String, default=now_iso),
)

password_resets = Table(
    "password_resets", metadata,
    Column("id", String, primary_key=True),
    Column("user_id", String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
    Column("token_hash", String, nullable=False, unique=True),
    Column("expires_at", String, nullable=False),
    Column("used", Boolean, nullable=False, default=False),
    Column("created_at", String, default=now_iso),
)

email_verifications = Table(
    "email_verifications", metadata,
    Column("id", String, primary_key=True),
    Column("user_id", String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
    Column("token_hash", String, nullable=False, unique=True),
    Column("expires_at", String, nullable=False),
    Column("used", Boolean, nullable=False, default=False),
    Column("created_at", String, default=now_iso),
)


# --------------------------------------------------------------------------- #
# Billing tables
# --------------------------------------------------------------------------- #
plans = Table(
    "plans", metadata,
    Column("id", String, primary_key=True),  # e.g. 'free', 'pro', 'scale'
    Column("name", String, nullable=False),
    Column("price_cents", Integer, nullable=False, default=0),
    Column("max_mailboxes", Integer, nullable=False, default=1),
    Column("daily_send_cap", Integer, nullable=False, default=40),
    Column("stripe_price_id", String, nullable=True),
    Column("is_active", Boolean, nullable=False, default=True),
)

subscriptions = Table(
    "subscriptions", metadata,
    Column("id", String, primary_key=True),
    Column("user_id", String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True),
    Column("plan_id", String, ForeignKey("plans.id"), nullable=False, default="free"),
    Column("status", String, nullable=False, default="active"),  # active | past_due | canceled
    Column("stripe_customer_id", String, nullable=True),
    Column("stripe_subscription_id", String, nullable=True),
    Column("current_period_end", String, nullable=True),
    Column("created_at", String, default=now_iso),
    Column("updated_at", String, default=now_iso),
)


# --------------------------------------------------------------------------- #
# Indexes — match the columns the app filters and orders by. Unique columns
# (email, *token_hash, subscriptions.user_id, warmup_schedules.mailbox_id) are
# already indexed by their UNIQUE constraint and are intentionally omitted.
# --------------------------------------------------------------------------- #
# Per-user and per-mailbox log queries always filter by owner and order by time.
Index("ix_logs_user_created", interaction_logs.c.user_id, interaction_logs.c.created_at)
Index("ix_logs_mailbox_created", interaction_logs.c.mailbox_id, interaction_logs.c.created_at)
# Mailbox fleet listing (per user) and org-scoped views.
Index("ix_mailboxes_user", mailboxes.c.user_id)
Index("ix_mailboxes_org", mailboxes.c.org_id)
# Team membership lookups.
Index("ix_org_members_user", org_members.c.user_id)
Index("ix_orgs_owner", organizations.c.owner_user_id)
Index("ix_invitations_org", invitations.c.org_id)
# Bulk refresh-token revocation on password reset / logout-all.
Index("ix_refresh_user", refresh_tokens.c.user_id)
Index("ix_stripe_customer", subscriptions.c.stripe_customer_id)
# System audit log is ordered by timestamp DESC.
Index("ix_syslogs_timestamp", system_logs.c.timestamp)
