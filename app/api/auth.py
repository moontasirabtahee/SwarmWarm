import logging
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import JWT_SECRET_KEY, JWT_ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES

logger = logging.getLogger("swarmwarm.auth")

from app.core.db import get_user_by_email, create_user

# Password hashing configuration
pwd_context = CryptContext(schemes=["sha256_crypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/token")

# Pydantic Schemas for Input Validation
class UserSignupRequest(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    id: str
    email: str
    role: str

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    user_id: Optional[str] = None
    email: Optional[str] = None
    role: Optional[str] = None

# FastAPI Router Object
router = APIRouter(prefix="/api/v1/auth", tags=["Authentication Controls"])

# Cryptographic Utilities
def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return encoded_jwt

from fastapi import Request

# Dependency Injection Guard
async def get_current_user(request: Request) -> TokenData:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    # Check Authorization header first
    auth_header = request.headers.get("Authorization")
    active_token = None
    if auth_header and auth_header.startswith("Bearer "):
         active_token = auth_header.split(" ")[1]
    
    # Fallback to query parameter (needed for native SSE event streams)
    if not active_token:
         active_token = request.query_params.get("token")
         
    if not active_token:
         raise credentials_exception
         
    try:
        payload = jwt.decode(active_token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        user_id: str = payload.get("sub")
        email: str = payload.get("email")
        role: str = payload.get("role", "user")
        if user_id is None or email is None:
            raise credentials_exception
        return TokenData(user_id=user_id, email=email, role=role)
    except JWTError:
        raise credentials_exception

# API Endpoints
@router.post("/signup", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def signup(payload: UserSignupRequest):
    """
    Registers a new tenant account, hashing raw passwords.
    """
    email_clean = payload.email.lower()
    existing_user = get_user_by_email(email_clean)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Account with this email already exists."
        )
        
    hashed_pwd = get_password_hash(payload.password)
    role = "admin" if email_clean == "ieee.dobby1998@gmail.com" else "user"
    
    user_record = create_user(email=email_clean, password_hash=hashed_pwd, role=role)
    logger.info(f"New user registered: {email_clean} (ID: {user_record['id']}, Role: {role})")
    
    return UserResponse(id=user_record["id"], email=email_clean, role=role)

@router.post("/token", response_model=Token)
@router.post("/login", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    Authenticates email credentials and issues secure JWT bearer tokens.
    """
    email_clean = form_data.username.lower()
    user = get_user_by_email(email_clean)
    if not user or not verify_password(form_data.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user["id"], "email": user["email"], "role": user["role"]},
        expires_delta=access_token_expires
    )
    logger.info(f"JWT Token issued successfully for user: {email_clean}")
    return {"access_token": access_token, "token_type": "bearer"}
