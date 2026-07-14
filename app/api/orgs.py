"""
Organizations / teams API.

Every user gets a personal workspace automatically. This router adds multi-member
collaboration: create workspaces, list members, invite teammates by email, and accept
invitations. Access to an org's data requires membership; managing members/invites
requires the owner or admin role within that org.
"""
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr

from app.api.auth import get_current_user, TokenData
from app.core import tokens
from app.core.settings import settings
from app.services.email_service import email_service
from app.core.db import (
    create_organization, get_organization, list_orgs_for_user, get_org_membership,
    add_org_member, list_org_members, remove_org_member, list_mailboxes_by_org,
    create_invitation, get_invitation, list_invitations_for_org, set_invitation_status,
    get_user_by_email, get_user_by_id,
)

logger = logging.getLogger("swarmwarm.orgs")
router = APIRouter(prefix="/api/v1/orgs", tags=["Organizations & Teams"])


# --------------------------------------------------------------------------- #
# Schemas
# --------------------------------------------------------------------------- #
class OrgCreateRequest(BaseModel):
    name: str


class OrgResponse(BaseModel):
    id: str
    name: str
    owner_user_id: str
    role: Optional[str] = None


class MemberResponse(BaseModel):
    id: str
    email: str
    full_name: Optional[str] = None
    role: str


class InviteRequest(BaseModel):
    email: EmailStr
    role: str = "member"


class InvitationResponse(BaseModel):
    id: str
    email: str
    role: str
    status: str
    expires_at: str


class AcceptRequest(BaseModel):
    token: str


# --------------------------------------------------------------------------- #
# Membership guards
# --------------------------------------------------------------------------- #
def _require_membership(org_id: str, user: TokenData) -> dict:
    if not get_organization(org_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found.")
    membership = get_org_membership(org_id, user.user_id)
    if not membership and user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not a member of this workspace.")
    return membership or {"role": "admin"}


def _require_manager(org_id: str, user: TokenData) -> dict:
    membership = _require_membership(org_id, user)
    if membership["role"] not in ("owner", "admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Owner or admin role required for this action.")
    return membership


# --------------------------------------------------------------------------- #
# Endpoints
# --------------------------------------------------------------------------- #
@router.get("", response_model=List[OrgResponse])
async def list_my_orgs(current_user: TokenData = Depends(get_current_user)):
    return [OrgResponse(**o) for o in list_orgs_for_user(current_user.user_id)]


@router.post("", response_model=OrgResponse, status_code=status.HTTP_201_CREATED)
async def create_org(payload: OrgCreateRequest, current_user: TokenData = Depends(get_current_user)):
    org = create_organization(name=payload.name, owner_user_id=current_user.user_id)
    return OrgResponse(**org, role="owner")


@router.get("/{org_id}/members", response_model=List[MemberResponse])
async def get_members(org_id: str, current_user: TokenData = Depends(get_current_user)):
    _require_membership(org_id, current_user)
    return [MemberResponse(**m) for m in list_org_members(org_id)]


@router.delete("/{org_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(org_id: str, user_id: str, current_user: TokenData = Depends(get_current_user)):
    _require_manager(org_id, current_user)
    org = get_organization(org_id)
    if org["owner_user_id"] == user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot remove the workspace owner.")
    remove_org_member(org_id, user_id)


@router.get("/{org_id}/mailboxes")
async def get_org_mailboxes(org_id: str, current_user: TokenData = Depends(get_current_user)):
    """All mailboxes in the workspace — visible to any member (org-level view)."""
    _require_membership(org_id, current_user)
    boxes = list_mailboxes_by_org(org_id)
    # Never expose encrypted credentials over the API.
    for b in boxes:
        b.pop("encrypted_password", None)
    return boxes


@router.get("/{org_id}/invitations", response_model=List[InvitationResponse])
async def get_invitations(org_id: str, current_user: TokenData = Depends(get_current_user)):
    _require_manager(org_id, current_user)
    return [InvitationResponse(id=i["id"], email=i["email"], role=i["role"],
                               status=i["status"], expires_at=i["expires_at"])
            for i in list_invitations_for_org(org_id)]


@router.post("/{org_id}/invitations", response_model=InvitationResponse, status_code=status.HTTP_201_CREATED)
async def invite_member(org_id: str, payload: InviteRequest, current_user: TokenData = Depends(get_current_user)):
    _require_manager(org_id, current_user)
    org = get_organization(org_id)

    # If the invitee is already a member, reject.
    existing_user = get_user_by_email(payload.email.lower())
    if existing_user and get_org_membership(org_id, existing_user["id"]):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User is already a member.")

    raw = tokens.generate_token()
    inv_id = create_invitation(
        org_id=org_id, email=payload.email.lower(), role=payload.role,
        token_hash=tokens.hash_token(raw), expires_at=tokens.expiry_iso(days=7),
        invited_by=current_user.user_id,
    )
    email_service.send_invitation(payload.email.lower(), raw, org["name"])
    logger.info("Invitation %s created for %s to org %s", inv_id, payload.email, org_id)
    return InvitationResponse(id=inv_id, email=payload.email.lower(), role=payload.role,
                              status="pending", expires_at=tokens.expiry_iso(days=7))


@router.post("/invitations/accept", status_code=status.HTTP_200_OK)
async def accept_invitation(payload: AcceptRequest, current_user: TokenData = Depends(get_current_user)):
    """Accept an invitation. The authenticated user's email must match the invite."""
    token_hash = tokens.hash_token(payload.token)
    inv = get_invitation(token_hash)
    if not inv or inv["status"] != "pending" or tokens.is_expired(inv["expires_at"]):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invitation is invalid or has expired.")

    user = get_user_by_id(current_user.user_id)
    if user["email"].lower() != inv["email"].lower():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="This invitation was issued to a different email address.")

    add_org_member(inv["org_id"], current_user.user_id, role=inv["role"])
    set_invitation_status(token_hash, "accepted")
    return {"detail": "Invitation accepted.", "org_id": inv["org_id"]}
