import os
import sys
from dotenv import load_dotenv
from app.core.security import encrypt_token
from app.workers.imap_engine import rescue_spam_emails, scan_unread_threads, IMAPConfig

# Load environment configs
load_dotenv()

def test_imap_ingress():
    print("================================================================================")
    print("                 SWARMWARM IMAP INGRESS & SPAM RESCUE DIAGNOSTIC")
    print("================================================================================")
    
    # Read test variables from .env
    host = os.getenv("TEST_IMAP_HOST")
    port = os.getenv("TEST_IMAP_PORT", "993")
    email_addr = os.getenv("TEST_MAILBOX_EMAIL")
    password = os.getenv("TEST_IMAP_PASSWORD")
    
    if not all([host, email_addr, password]):
        print("[-] DIAGNOSTIC INTERRUPTED: Missing test configurations in your .env file.")
        print("To run real IMAP socket checks, define the following variables in your .env:")
        print("  TEST_IMAP_HOST=imap.gmail.com")
        print("  TEST_IMAP_PORT=993")
        print("  TEST_MAILBOX_EMAIL=your_test@gmail.com")
        print("  TEST_IMAP_PASSWORD=your_app_password_token")
        print("\nSkipping live socket diagnostic check. (Requirements mapped successfully).")
        return
        
    try:
        # Encrypt the password first to simulate database state retrieval
        print("[TEST SECURE] Encrypting test credential App Password...")
        enc_password = encrypt_token(password)
        
        # Instantiate IMAPConfig model
        config = IMAPConfig(
            imap_host=host,
            imap_port=int(port),
            mailbox_email=email_addr,
            encrypted_password=enc_password,
            provider="custom"
        )
        
        # 1. Run Spam Rescue Diagnostic
        print(f"\n[TEST IMAP] Scanning Spam folders on behalf of {email_addr}...")
        rescued = rescue_spam_emails(config, search_subject="SwarmWarm")
        print(f"[+] IMAP RESCUE COMPLETE: Moved {len(rescued)} warmup messages to INBOX. Rescued IDs: {rescued}")
        
        # 2. Run Inbox Thread Scanner
        print(f"\n[TEST IMAP] Fetching unread warmup threads from {email_addr}...")
        threads = scan_unread_threads(config, search_subject="SwarmWarm")
        print(f"[+] IMAP SCAN COMPLETE: Retrieved {len(threads)} unread threads.")
        for idx, t in enumerate(threads, 1):
             print(f" Thread {idx}: ID: {t['message_id']} | Subject: {t['subject']} | Length: {len(t['body'])} chars")
             
    except Exception as e:
        print(f"[-] IMAP DIAGNOSTIC FAILED: {e}")
        sys.exit(1)

if __name__ == "__main__":
    test_imap_ingress()
