"""
Billing API — plans, subscription status, checkout, and Stripe webhook.

Runs in two modes:

* Dev mode (no STRIPE_SECRET_KEY): `/checkout` activates the chosen plan immediately
  so the flow is testable without Stripe. Useful for demos and CI.
* Live mode (STRIPE_SECRET_KEY set): `/checkout` creates a real Stripe Checkout
  Session and `/webhook` verifies the signature and syncs subscription state.
"""
import json
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from app.api.auth import get_current_user, TokenData
from app.core.settings import settings
from app.core.db import (
    list_plans, get_plan, get_subscription_by_user, ensure_subscription,
    set_subscription_plan, count_mailboxes_by_user, get_user_by_stripe_customer,
)
from app.services.billing_service import get_user_plan

logger = logging.getLogger("swarmwarm.billing")
router = APIRouter(prefix="/api/v1/billing", tags=["Billing & Subscriptions"])


class PlanResponse(BaseModel):
    id: str
    name: str
    price_cents: int
    max_mailboxes: int
    daily_send_cap: int


class SubscriptionResponse(BaseModel):
    plan_id: str
    plan_name: str
    status: str
    max_mailboxes: int
    daily_send_cap: int
    mailboxes_used: int
    current_period_end: Optional[str] = None


class CheckoutRequest(BaseModel):
    plan_id: str


@router.get("/plans", response_model=List[PlanResponse])
async def get_plans():
    return [PlanResponse(**p) for p in list_plans()]


@router.get("/subscription", response_model=SubscriptionResponse)
async def get_subscription(current_user: TokenData = Depends(get_current_user)):
    sub = get_subscription_by_user(current_user.user_id) or ensure_subscription(current_user.user_id)
    plan = get_user_plan(current_user.user_id)
    return SubscriptionResponse(
        plan_id=plan["id"],
        plan_name=plan["name"],
        status=sub["status"],
        max_mailboxes=plan["max_mailboxes"],
        daily_send_cap=plan["daily_send_cap"],
        mailboxes_used=count_mailboxes_by_user(current_user.user_id),
        current_period_end=sub.get("current_period_end"),
    )


@router.post("/checkout")
async def create_checkout(payload: CheckoutRequest, current_user: TokenData = Depends(get_current_user)):
    """
    Start an upgrade. Live mode returns a Stripe Checkout URL; dev mode activates
    the plan immediately and returns it as already active.
    """
    plan = get_plan(payload.plan_id)
    if not plan or not plan["is_active"]:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown plan.")

    if not settings.STRIPE_SECRET_KEY:
        # Dev/test mode — no external call, activate directly.
        set_subscription_plan(current_user.user_id, plan["id"], status="active")
        logger.info("[billing:dev] %s activated plan %s", current_user.email, plan["id"])
        return {"mode": "dev", "checkout_url": None, "plan_id": plan["id"], "status": "active"}

    # Live mode — create a Stripe Checkout Session.
    try:
        import stripe
        stripe.api_key = settings.STRIPE_SECRET_KEY
        session = stripe.checkout.Session.create(
            mode="subscription",
            line_items=[{"price": plan["stripe_price_id"], "quantity": 1}],
            success_url=f"{settings.PUBLIC_BASE_URL}/?billing=success",
            cancel_url=f"{settings.PUBLIC_BASE_URL}/?billing=cancel",
            client_reference_id=current_user.user_id,
            customer_email=current_user.email,
            metadata={"user_id": current_user.user_id, "plan_id": plan["id"]},
        )
        return {"mode": "live", "checkout_url": session.url, "plan_id": plan["id"]}
    except Exception as exc:
        logger.error("Stripe checkout failed: %s", exc)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Billing provider error.")


@router.post("/webhook")
async def stripe_webhook(request: Request):
    """
    Stripe webhook receiver. Live mode verifies the signature; dev mode accepts a
    plain JSON body {user_id, plan_id, status} so subscription sync is testable.
    """
    raw = await request.body()

    if settings.STRIPE_SECRET_KEY and settings.STRIPE_WEBHOOK_SECRET:
        try:
            import stripe
            event = stripe.Webhook.construct_event(
                raw, request.headers.get("Stripe-Signature", ""), settings.STRIPE_WEBHOOK_SECRET
            )
        except Exception as exc:
            logger.error("Stripe webhook signature verification failed: %s", exc)
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid signature.")

        etype = event["type"]
        obj = event["data"]["object"]
        if etype == "checkout.session.completed":
            user_id = (obj.get("metadata") or {}).get("user_id") or obj.get("client_reference_id")
            plan_id = (obj.get("metadata") or {}).get("plan_id", "pro")
            if user_id:
                set_subscription_plan(user_id, plan_id, status="active",
                                      stripe_customer_id=obj.get("customer"),
                                      stripe_subscription_id=obj.get("subscription"))
        elif etype in ("customer.subscription.deleted", "customer.subscription.canceled"):
            sub = get_user_by_stripe_customer(obj.get("customer"))
            if sub:
                set_subscription_plan(sub["user_id"], "free", status="canceled")
        return {"received": True}

    # Dev mode
    try:
        body = json.loads(raw or b"{}")
    except json.JSONDecodeError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON.")
    user_id = body.get("user_id")
    plan_id = body.get("plan_id", "pro")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="user_id required in dev mode.")
    set_subscription_plan(user_id, plan_id, status=body.get("status", "active"))
    return {"received": True, "mode": "dev"}
