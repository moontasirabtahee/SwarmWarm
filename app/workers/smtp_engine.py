import time
import uuid
import random
import smtplib
from email.mime.text import MIMEText
from pydantic import BaseModel, Field, EmailStr
from app.core.security import decrypt_token

class SMTPConfig(BaseModel):
    """
    Pydantic schema capturing SMTP connection details.
    """
    smtp_host: str = Field(..., description="SMTP server hostname (e.g. smtp.gmail.com)")
    smtp_port: int = Field(..., description="SMTP server port (e.g. 465, 587)")
    sender_email: EmailStr = Field(..., description="Authenticated sender email address")
    encrypted_password: str = Field(..., description="Base64 GCM encrypted app password")
    provider: str = Field("custom", description="Email provider (google, microsoft, custom)")
    use_ssl: bool = Field(True, description="Establish direct SSL connection if True, else use STARTTLS")

def send_warmup_email(config: SMTPConfig, recipient: str, subject: str, body: str, in_reply_to: str = None, references: str = None) -> dict:
    """
    Sends a warm-up email using SMTP, incorporating security decryption, jitter,
    and standard-compliant RFC Message-ID and threading headers.
    """
    # 1. Apply organic connection jitter (15s to 180s in production)
    jitter = random.randint(15, 180)
    print(f"[SMTP JITTER] Applying connection sleep offset: {jitter} seconds...")
    time.sleep(jitter)
    
    # 2. Decrypt credentials using core security subsystem
    try:
        decrypted_password = decrypt_token(config.encrypted_password)
    except Exception as e:
        raise ValueError(f"SMTP Authentication failure: Credential decryption failed. {e}")
        
    # 3. Construct standard-compliant MIME text message
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = config.sender_email
    msg["To"] = recipient
    
    # Set threading headers if this is a contextual reply
    if in_reply_to:
        msg["In-Reply-To"] = in_reply_to
    if references:
        msg["References"] = references
        
    # Generate explicit RFC-compliant Message-ID header: <uuid@domain>
    sender_domain = config.sender_email.split("@")[-1]
    unique_message_id = f"<{uuid.uuid4()}@{sender_domain}>"
    msg["Message-ID"] = unique_message_id
    
    # 4. Establish network connection and dispatch
    print(f"[SMTP CONNECT] Establishing socket link to {config.smtp_host}:{config.smtp_port}...")
    try:
        if config.use_ssl or config.smtp_port == 465:
            server = smtplib.SMTP_SSL(config.smtp_host, config.smtp_port, timeout=15)
        else:
            server = smtplib.SMTP(config.smtp_host, config.smtp_port, timeout=15)
            server.ehlo()
            print("[SMTP TLS] Initiating STARTTLS handshake sequence...")
            server.starttls()
            server.ehlo()
            
        print("[SMTP AUTH] Authenticating SMTP credentials...")
        server.login(config.sender_email, decrypted_password)
        
        print("[SMTP SEND] Dispatched warmup message payload...")
        server.send_message(msg)
        server.quit()
        print("[SMTP SUCCESS] Handshake complete and connection closed gracefully.")
        return {"status": "success", "message_id": unique_message_id}
        
    except Exception as e:
        print(f"[SMTP ERROR] Outbound connection handshake failed: {e}")
        raise ConnectionError(f"SMTP connection failed: {e}")
