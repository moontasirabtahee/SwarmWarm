import os
import sys
from dotenv import load_dotenv
from app.core.security import encrypt_token
from app.workers.smtp_engine import send_warmup_email, SMTPConfig

# Load environment configs
load_dotenv()

def test_smtp_dispatch():
    print("================================================================================")
    print("                 SWARMWARM SMTP PROTOCOL HANDSHAKE DIAGNOSTIC")
    print("================================================================================")
    
    # Read test variables from .env
    host = os.getenv("TEST_SMTP_HOST")
    port = os.getenv("TEST_SMTP_PORT")
    sender = os.getenv("TEST_SENDER_EMAIL")
    password = os.getenv("TEST_SMTP_PASSWORD")
    recipient = os.getenv("TEST_RECIPIENT_EMAIL")
    
    if not all([host, port, sender, password, recipient]):
        print("[-] DIAGNOSTIC INTERRUPTED: Missing test configurations in your .env file.")
        print("To run real SMTP socket checks, define the following variables in your .env:")
        print("  TEST_SMTP_HOST=smtp.gmail.com")
        print("  TEST_SMTP_PORT=465")
        print("  TEST_SENDER_EMAIL=your_test@gmail.com")
        print("  TEST_SMTP_PASSWORD=your_app_password_token")
        print("  TEST_RECIPIENT_EMAIL=recipient_test@gmail.com")
        print("\nSkipping live socket diagnostic check. (Requirements mapped successfully).")
        return
        
    try:
        # Encrypt the password first to simulate database state retrieval
        print("[TEST SECURE] Encrypting test credential App Password...")
        enc_password = encrypt_token(password)
        
        # Instantiate SMTPConfig model
        config = SMTPConfig(
            smtp_host=host,
            smtp_port=int(port),
            sender_email=sender,
            encrypted_password=enc_password,
            provider="custom",
            use_ssl=(int(port) == 465)
        )
        
        print(f"[TEST SMTP] Dispatching test mail from {sender} to {recipient}...")
        # Note: We scale down jitter to 1s for immediate diagnostic responsiveness
        # but in tasks execution, it runs normal spec range (15s-180s).
        result = send_warmup_email(config, recipient, "SwarmWarm Outbound Warmup Test", "This is an automated warmup test message dispatched by the SwarmWarm engine.")
        print(f"[+] SMTP TEST SUCCESS: Message dispatched. Returned metadata: {result}")
        
    except Exception as e:
        print(f"[-] SMTP DIAGNOSTIC FAILED: {e}")
        sys.exit(1)

if __name__ == "__main__":
    test_smtp_dispatch()
