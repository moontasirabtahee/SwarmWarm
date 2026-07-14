"""
Billing / plan-entitlement logic.

Resolves a user's effective plan (via their subscription, defaulting to Free) and
provides the quota checks the rest of the app enforces:

* mailbox count ceiling  (plan.max_mailboxes)
* daily send ceiling     (plan.daily_send_cap)
"""
from typing import Tuple

from app.core.db import (
    get_subscription_by_user, ensure_subscription, get_plan, count_mailboxes_by_user,
)

# Used only if the plans table somehow has no matching row (defensive).
_FREE_FALLBACK = {
    "id": "free", "name": "Free", "price_cents": 0,
    "max_mailboxes": 2, "daily_send_cap": 40,
}


def get_user_plan(user_id: str) -> dict:
    sub = get_subscription_by_user(user_id) or ensure_subscription(user_id)
    return get_plan(sub["plan_id"]) or _FREE_FALLBACK


def can_add_mailbox(user_id: str) -> Tuple[bool, dict, int]:
    """Return (allowed, plan, current_count)."""
    plan = get_user_plan(user_id)
    count = count_mailboxes_by_user(user_id)
    return count < plan["max_mailboxes"], plan, count


def effective_daily_limit(user_id: str, requested_limit: int) -> int:
    """Clamp a requested per-mailbox daily send limit to the plan's cap."""
    plan = get_user_plan(user_id)
    return min(requested_limit, plan["daily_send_cap"])
