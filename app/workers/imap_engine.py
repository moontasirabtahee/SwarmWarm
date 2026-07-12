import email
import imaplib
import email.utils
from email.header import decode_header
from pydantic import BaseModel, Field, EmailStr
from app.core.security import decrypt_token

class IMAPConfig(BaseModel):
    """
    Pydantic schema capturing IMAP connection details.
    """
    imap_host: str = Field(..., description="IMAP server hostname (e.g. imap.gmail.com)")
    imap_port: int = Field(993, description="IMAP server port (e.g. 993)")
    mailbox_email: EmailStr = Field(..., description="Email address of the mailbox to connect to")
    encrypted_password: str = Field(..., description="Base64 GCM encrypted app password")
    provider: str = Field("custom", description="Email provider (google, microsoft, custom)")

def connect_imap(config: IMAPConfig) -> imaplib.IMAP4_SSL:
    """
    Saves decrypted credentials and logs into IMAP4_SSL securely.
    """
    try:
        decrypted_password = decrypt_token(config.encrypted_password)
    except Exception as e:
        raise ValueError(f"IMAP Authentication failure: Credential decryption failed. {e}")
        
    print(f"[IMAP CONNECT] Connecting to {config.imap_host}:{config.imap_port}...")
    try:
        mailbox = imaplib.IMAP4_SSL(config.imap_host, config.imap_port, timeout=15)
        print("[IMAP AUTH] Logging in...")
        mailbox.login(config.mailbox_email, decrypted_password)
        return mailbox
    except Exception as e:
        raise ConnectionError(f"IMAP connection failed: {e}")

def rescue_spam_emails(config: IMAPConfig, search_subject: str = "SwarmWarm") -> list:
    """
    Searches for warmup emails inside Spam/Junk directories, moves them to INBOX,
    and flags them as \\Seen and \\Important.
    """
    mailbox = connect_imap(config)
    rescued_message_ids = []
    
    # Major folder patterns for Spam across Google, Microsoft, and custom environments
    spam_folders = ["SPAM", "JUNK", "[Gmail]/Spam", "Junk Email", "Spam Folders"]
    
    for folder in spam_folders:
        try:
            print(f"[IMAP FOLDER] Checking directory: {folder}")
            status, _ = mailbox.select(folder)
            if status != 'OK':
                continue
                
            # Search by Subject containing search_subject
            status, data = mailbox.search(None, f'(SUBJECT "{search_subject}")')
            if status != 'OK' or not data[0]:
                print(f"[IMAP SEARCH] No warmup items located in folder: {folder}")
                continue
                
            message_numbers = data[0].split()
            print(f"[IMAP RESCUE] Located {len(message_numbers)} trapped emails in {folder}!")
            
            for num in message_numbers:
                # Retrieve Message-ID header
                status, msg_data = mailbox.fetch(num, '(BODY[HEADER.FIELDS (MESSAGE-ID)])')
                msg_id_val = "Unknown"
                if status == 'OK' and msg_data[0]:
                    msg_id_header = email.message_from_bytes(msg_data[0][1])
                    msg_id_val = msg_id_header.get("Message-ID", "Unknown").strip()
                
                print(f"[IMAP COPY] Rescuing Message-ID: {msg_id_val} -> Copying to INBOX...")
                # Copy to INBOX
                copy_status, _ = mailbox.copy(num, "INBOX")
                if copy_status == 'OK':
                    # Set the original trapped item state to Deleted
                    mailbox.store(num, '+FLAGS', '\\Deleted')
                    rescued_message_ids.append(msg_id_val)
                    
            # Expunge deleted items from current folder
            mailbox.expunge()
            
        except Exception as folder_err:
            print(f"[IMAP FOLDER ERROR] Error scanning directory {folder}: {folder_err}")
            
    # Connect back to INBOX to flag newly moved elements
    try:
        mailbox.select("INBOX")
        for msg_id in rescued_message_ids:
            # Search inbox for matching Message-ID
            status, data = mailbox.search(None, f'HEADER Message-ID "{msg_id}"')
            if status == 'OK' and data[0]:
                for num in data[0].split():
                    print(f"[IMAP FLAG] Marking rescued message {msg_id} as \\Seen and \\Important...")
                    # Set Seen and Important flags
                    mailbox.store(num, '+FLAGS', '\\Seen')
                    # 'Important' is mapped via $Phishing or custom tag depends on client, we apply standard Seen
                    mailbox.store(num, '+FLAGS', 'Important')
    except Exception as flag_err:
        print(f"[IMAP FLAG ERROR] Failed to adjust flags in Inbox: {flag_err}")
        
    mailbox.logout()
    return rescued_message_ids

def scan_unread_threads(config: IMAPConfig, search_subject: str = "SwarmWarm") -> list:
    """
    Inspects the INBOX for unread warmup messages and extracts clean body text.
    """
    mailbox = connect_imap(config)
    thread_buffers = []
    
    try:
        print("[IMAP SCAN] Scanning INBOX for unread warmup threads...")
        mailbox.select("INBOX")
        
        # Search for UNSEEN emails with the target subject
        status, data = mailbox.search(None, f'(UNSEEN SUBJECT "{search_subject}")')
        if status == 'OK' and data[0]:
            message_numbers = data[0].split()
            print(f"[IMAP SCAN] Located {len(message_numbers)} unread emails.")
            
            for num in message_numbers:
                status, msg_data = mailbox.fetch(num, '(RFC822)')
                if status == 'OK' and msg_data[0]:
                    raw_email = msg_data[0][1]
                    msg = email.message_from_bytes(raw_email)
                    
                    # Extract subject and body
                    subject_header = msg.get("Subject", "")
                    decoded_subject = ""
                    for part, encoding in decode_header(subject_header):
                        if isinstance(part, bytes):
                            decoded_subject += part.decode(encoding or "utf-8")
                        else:
                            decoded_subject += str(part)
                            
                    msg_id = msg.get("Message-ID", "Unknown").strip()
                    from_header = msg.get("From", "")
                    from_name, sender_email = email.utils.parseaddr(from_header)
                    
                    # Extract body text
                    body = ""
                    if msg.is_multipart():
                        for part in msg.walk():
                            content_type = part.get_content_type()
                            content_disp = str(part.get("Content-Disposition"))
                            if content_type == "text/plain" and "attachment" not in content_disp:
                                body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                                break
                    else:
                        body = msg.get_payload(decode=True).decode('utf-8', errors='ignore')
                        
                    thread_buffers.append({
                        "message_id": msg_id,
                        "sender_email": sender_email,
                        "subject": decoded_subject,
                        "body": body.strip()
                    })
                    
    except Exception as e:
        print(f"[IMAP SCAN ERROR] Failed to fetch thread buffers: {e}")
        
    mailbox.logout()
    return thread_buffers
