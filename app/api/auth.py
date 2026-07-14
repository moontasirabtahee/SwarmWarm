import logging
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr
from jose import JWTError, jwt

from app.core.config import (
    JWT_SECRET_KEY, JWT_ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES, REFRESH_TOKEN_EXPIRE_DAYS,
)
from app.core.settings import settings
from app.core.passwords import hash_password, verify_password as _verify_password
from app.core import tokens
from app.services.email_service import email_service

logger = logging.getLogger("swarmwarm.auth")

from app.core.db import (
    get_user_by_email, get_user_by_id, create_user, update_user_password, set_user_verified,
    create_refresh_token, get_refresh_token, revoke_refresh_token, revoke_all_refresh_tokens,
    create_password_reset, get_password_reset, mark_password_reset_used,
    create_email_verification, get_email_verification, mark_email_verification_used,
    ensure_subscription, ensure_personal_org,
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/token")


# --------------------------------------------------------------------------- #
# Schemas
# --------------------------------------------------------------------------- #
class UserSignupRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: Optional[str] = None


class UserResponse(BaseModel):
    id: str
    email: str
    role: str
    is_verified: bool = False


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    refresh_token: Optional[str] = None
    expires_in: int = ACCESS_TOKEN_EXPIRE_MINUTES * 60


class TokenData(BaseModel):
    user_id: Optional[str] = None
    email: Optional[str] = None
    role: Optional[str] = None


class RefreshRequest(BaseModel):
    refresh_token: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


router = APIRouter(prefix="/api/v1/auth", tags=["Authentication Controls"])


# --------------------------------------------------------------------------- #
# Password + JWT utilities
# --------------------------------------------------------------------------- #
def get_password_hash(password: str) -> str:
    return hash_password(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return _verify_password(plain_password, hashed_password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def _issue_refresh_token(user_id: str) -> str:
    raw = tokens.generate_token()
    create_refresh_token(
        user_id=user_id,
        token_hash=tokens.hash_token(raw),
        expires_at=tokens.expiry_iso(days=REFRESH_TOKEN_EXPIRE_DAYS),
    )
    return raw


def _issue_token_pair(user: dict) -> Token:
    access = create_access_token(
        data={"sub": user["id"], "email": user["email"], "role": user["role"]}
    )
    refresh = _issue_refresh_token(user["id"])
    return Token(access_token=access, refresh_token=refresh)


# --------------------------------------------------------------------------- #
# Login rate limiting (in-memory sliding window, keyed by email+client IP)
# --------------------------------------------------------------------------- #
_login_attempts: "defaultdict[str, deque]" = defaultdict(deque)
_LOGIN_ATTEMPTS_MAX_KEYS = 4096  # cap memory; sweep stale entries past this size


def _prune_login_attempts(now: float):
    """Drop keys whose attempts have all aged out (prevents unbounded growth)."""
    if len(_login_attempts) < _LOGIN_ATTEMPTS_MAX_KEYS:
        return
    window = settings.LOGIN_WINDOW_SECONDS
    stale = [k for k, dq in _login_attempts.items() if not dq or now - dq[-1] > window]
    for k in stale:
        _login_attempts.pop(k, None)


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("X-Forwarded-For")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _rate_limit_key(email: str, request: Request) -> str:
    return f"{email.lower()}|{_client_ip(request)}"


def _check_rate_limit(key: str):
    window = settings.LOGIN_WINDOW_SECONDS
    now = time.time()
    _prune_login_attempts(now)
    attempts = _login_attempts[key]
    while attempts and now - attempts[0] > window:
        attempts.popleft()
    if len(attempts) >= settings.LOGIN_MAX_ATTEMPTS:
        retry_after = int(window - (now - attempts[0])) if attempts else window
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed login attempts. Please try again later.",
            headers={"Retry-After": str(max(1, retry_after))},
        )


def _record_failure(key: str):
    _login_attempts[key].append(time.time())


def _reset_attempts(key: str):
    _login_attempts.pop(key, None)


# --------------------------------------------------------------------------- #
# Auth dependency guard
# --------------------------------------------------------------------------- #
async def get_current_user(request: Request) -> TokenData:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    auth_header = request.headers.get("Authorization")
    active_token = None
    if auth_header and auth_header.startswith("Bearer "):
        active_token = auth_header.split(" ")[1]
    if not active_token:
        # Fallback to query parameter (needed for native SSE event streams)
        active_token = request.query_params.get("token")
    if not active_token:
        raise credentials_exception

    try:
        payload = jwt.decode(active_token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        user_id = payload.get("sub")
        email = payload.get("email")
        role = payload.get("role", "user")
        if user_id is None or email is None:
            raise credentials_exception
        return TokenData(user_id=user_id, email=email, role=role)
    except JWTError:
        raise credentials_exception


# --------------------------------------------------------------------------- #
# Endpoints
# --------------------------------------------------------------------------- #
@router.post("/signup", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def signup(payload: UserSignupRequest):
    """Registers a new tenant account and dispatches an email-verification link."""
    email_clean = payload.email.lower()
    if get_user_by_email(email_clean):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Account with this email already exists.")

    role = "admin" if email_clean in [e.lower() for e in settings.ADMIN_EMAILS] else "user"
    user_record = create_user(
        email=email_clean, password_hash=get_password_hash(payload.password),
        role=role, is_verified=False, full_name=payload.full_name,
    )

    # Every new account starts on the Free plan with a personal workspace.
    ensure_subscription(user_record["id"], plan_id="free")
    ensure_personal_org(user_record["id"], email_clean)

    # Issue and email a verification token.
    raw = tokens.generate_token()
    create_email_verification(user_record["id"], tokens.hash_token(raw), tokens.expiry_iso(days=2))
    email_service.send_verification(email_clean, raw)

    logger.info(f"New user registered: {email_clean} (ID: {user_record['id']}, Role: {role})")
    return UserResponse(id=user_record["id"], email=email_clean, role=role, is_verified=False)


@router.post("/token", response_model=Token)
@router.post("/login", response_model=Token)
async def login_for_access_token(request: Request, form_data: OAuth2PasswordRequestForm = Depends()):
    """Authenticates credentials, applies rate limiting, and issues access + refresh tokens."""
    email_clean = form_data.username.lower()
    rl_key = _rate_limit_key(email_clean, request)
    _check_rate_limit(rl_key)

    user = get_user_by_email(email_clean)
    if not user or not verify_password(form_data.password, user["password_hash"]):
        _record_failure(rl_key)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    _reset_attempts(rl_key)
    logger.info(f"JWT token issued successfully for user: {email_clean}")
    return _issue_token_pair(user)


@router.post("/refresh", response_model=Token)
async def refresh_access_token(payload: RefreshRequest):
    """Exchanges a valid refresh token for a new access token (with refresh rotation)."""
    invalid = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token")
    token_hash = tokens.hash_token(payload.refresh_token)
    record = get_refresh_token(token_hash)
    if not record or record["revoked"] or tokens.is_expired(record["expires_at"]):
        raise invalid

    user = get_user_by_id(record["user_id"])
    if not user:
        raise invalid

    # Rotate: revoke the used refresh token and issue a fresh pair.
    revoke_refresh_token(token_hash)
    return _issue_token_pair(user)


@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout(payload: RefreshRequest):
    """Revokes a refresh token server-side (client also clears its access token)."""
    revoke_refresh_token(tokens.hash_token(payload.refresh_token))
    return {"detail": "Logged out."}


@router.get("/verify-email")
async def verify_email(token: str):
    """Confirms a user's email address from the verification link."""
    token_hash = tokens.hash_token(token)
    record = get_email_verification(token_hash)
    if not record or record["used"] or tokens.is_expired(record["expires_at"]):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Verification link is invalid or has expired.")
    set_user_verified(record["user_id"], True)
    mark_email_verification_used(token_hash)
    return {"detail": "Email verified successfully. You can now sign in."}


@router.post("/password/forgot", status_code=status.HTTP_200_OK)
async def forgot_password(payload: ForgotPasswordRequest):
    """Starts a password reset. Always returns 200 to avoid leaking which emails exist."""
    user = get_user_by_email(payload.email.lower())
    if user:
        raw = tokens.generate_token()
        create_password_reset(user["id"], tokens.hash_token(raw), tokens.expiry_iso(hours=1))
        email_service.send_password_reset(user["email"], raw)
    return {"detail": "If that account exists, a reset link has been sent."}


@router.post("/password/reset", status_code=status.HTTP_200_OK)
async def reset_password(payload: ResetPasswordRequest):
    """Completes a password reset and revokes all existing refresh tokens."""
    if len(payload.new_password) < 6:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Password must be at least 6 characters.")
    token_hash = tokens.hash_token(payload.token)
    record = get_password_reset(token_hash)
    if not record or record["used"] or tokens.is_expired(record["expires_at"]):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Reset link is invalid or has expired.")
    update_user_password(record["user_id"], get_password_hash(payload.new_password))
    mark_password_reset_used(token_hash)
    revoke_all_refresh_tokens(record["user_id"])  # force re-login everywhere
    return {"detail": "Password updated. Please sign in with your new password."}


@router.get("/me", response_model=UserResponse)
async def read_me(current_user: TokenData = Depends(get_current_user)):
    user = get_user_by_id(current_user.user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    return UserResponse(id=user["id"], email=user["email"], role=user["role"],
                        is_verified=bool(user.get("is_verified")))
