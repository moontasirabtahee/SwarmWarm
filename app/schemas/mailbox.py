from pydantic import BaseModel, Field, EmailStr
from typing import Optional

class MailboxOnboardRequest(BaseModel):
    """
    Onboarding data validation schema (ensures valid connection coordinates).
    """
    email: EmailStr = Field(..., description="Outbound sender email address")
    smtp_host: str = Field(..., description="SMTP server address")
    smtp_port: int = Field(..., description="SMTP server port (e.g. 465, 587)")
    imap_host: str = Field(..., description="IMAP server address")
    imap_port: int = Field(993, description="IMAP server port (e.g. 993)")
    app_password: str = Field(..., description="Plaintext app password token")
    provider: str = Field("custom", description="Email provider type (google, microsoft, custom)")
    use_ssl: bool = Field(True, description="Establish secure direct SSL socket connection if True")

class MailboxResponse(BaseModel):
    """
    Standard response representation (excludes password strings).
    """
    id: str
    user_id: str
    email: str
    smtp_host: str
    smtp_port: int
    imap_host: str
    imap_port: int
    provider: str
    use_ssl: bool
    is_active: bool
