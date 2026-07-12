import logging
import asyncio
from app.core.celery_app import app
from app.workers.smtp_engine import send_warmup_email, SMTPConfig
from app.workers.imap_engine import rescue_spam_emails, scan_unread_threads, IMAPConfig
from app.services.ai_service import AIService

# Set up logging configuration
logger = logging.getLogger("swarmwarm.tasks")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

from app.core.db import MAILBOXES

def get_mailbox_record(mailbox_id: str) -> dict:
    """
    Simulates database retrieval query for mailbox parameters.
    """
    record = MAILBOXES.get(mailbox_id)
    if not record:
        raise ValueError(f"Mailbox record not found in database: {mailbox_id}")
    return record

def set_mailbox_inactive_in_db(mailbox_id: str, reason: str):
    """
    Simulates writing a DB update queries to disable an inactive mailbox.
    """
    logger.error(f"[DATABASE UPDATE] Disabling mailbox {mailbox_id}. Reason: {reason}")
    if mailbox_id in MAILBOXES:
        MAILBOXES[mailbox_id]["is_active"] = False

@app.task(bind=True, max_retries=3, default_retry_delay=300)
def execute_smtp_send_task(self, sender_mailbox_id: str, recipient_email: str):
    """
    Decoupled Celery task executing outbound secure SMTP dispatch with dynamic AI prompt starters.
    """
    logger.info(f"Starting SMTP send task. Sender ID: {sender_mailbox_id} | Recipient: {recipient_email}")
    
    try:
        record = get_mailbox_record(sender_mailbox_id)
        if not record["is_active"]:
            logger.warning(f"Aborting SMTP task: Mailbox {sender_mailbox_id} is inactive.")
            return {"status": "skipped", "reason": "mailbox_inactive"}
            
        # Bind configs to Pydantic schemas
        config = SMTPConfig(
            smtp_host=record["smtp_host"],
            smtp_port=record["smtp_port"],
            sender_email=record["email"],
            encrypted_password=record["encrypted_password"],
            provider=record["provider"],
            use_ssl=record["use_ssl"]
        )
        
        # 1. Dynamically generate organic content using the AI prompt engine
        logger.info("Accessing Local AI service to generate introductory email content...")
        ai_service = AIService()
        try:
             ai_payload = asyncio.run(ai_service.generate_thread_starter())
             body_text = ai_payload.get("body", "Default backup warmup content.")
        except Exception as ai_err:
             logger.warning(f"Local AI inference tunnel failed: {ai_err}. Falling back to default baseline text.")
             body_text = "Checking in to see if we are scheduled for the database schema review this week."
             
        # 2. Dispatch SMTP warmup using verified outbound module
        result = send_warmup_email(config, recipient_email, "Warmup Sync Request", body_text)
        logger.info(f"SMTP send task completed successfully. Message-ID: {result['message_id']}")
        return {"status": "success", "message_id": result["message_id"]}
        
    except (ConnectionError, TimeoutError) as conn_exc:
        retry_delay = self.default_retry_delay * (2 ** self.request.retries)
        logger.warning(f"Transient error encountered: {conn_exc}. Retrying task in {retry_delay}s...")
        raise self.retry(exc=conn_exc, countdown=retry_delay)
        
    except ValueError as auth_exc:
        logger.error(f"Permanent authentication error: {auth_exc}. Deactivating mailbox.")
        set_mailbox_inactive_in_db(sender_mailbox_id, str(auth_exc))
        return {"status": "failed", "reason": "auth_failure", "error": str(auth_exc)}
        
    except Exception as e:
        logger.error(f"Unhandled exception during SMTP task: {e}")
        raise e

@app.task(bind=True, max_retries=3, default_retry_delay=300)
def execute_imap_rescue_task(self, mailbox_id: str, expected_message_id: str):
    """
    Decoupled Celery task executing inbound IMAP rescues, thread scanning,
    and context-aware AI threaded reply processing.
    """
    logger.info(f"Starting IMAP rescue task. Mailbox ID: {mailbox_id} | Expected Message-ID: {expected_message_id}")
    
    try:
        record = get_mailbox_record(mailbox_id)
        if not record["is_active"]:
            logger.warning(f"Aborting IMAP task: Mailbox {mailbox_id} is inactive.")
            return {"status": "skipped", "reason": "mailbox_inactive"}
            
        config = IMAPConfig(
            imap_host=record["imap_host"],
            imap_port=record["imap_port"],
            mailbox_email=record["email"],
            encrypted_password=record["encrypted_password"],
            provider=record["provider"]
        )
        
        # 1. Execute IMAP search, move, and flag update sequences on Spam folders
        rescued = rescue_spam_emails(config, search_subject="SwarmWarm")
        logger.info(f"IMAP rescue search completed. Rescued count: {len(rescued)}")
        
        # 2. Scan Inbox for unread messages to reply to contextually
        logger.info("Scanning Inbox directory for incoming warmup thread loops...")
        unread_threads = scan_unread_threads(config, search_subject="SwarmWarm")
        
        ai_service = AIService()
        replies_dispatched = []
        
        for thread in unread_threads:
             incoming_body = thread["body"]
             thread_msg_id = thread["message_id"]
             thread_sender = thread["sender_email"]
             thread_subject = thread["subject"]
             
             logger.info(f"Processing unread thread from: {thread_sender}...")
             
             # Generate smart reply
             try:
                  reply_text = asyncio.run(ai_service.generate_thread_reply(incoming_body))
             except Exception as ai_err:
                  logger.warning(f"AI Smart Reply generation failed: {ai_err}. Using generic confirmation template.")
                  reply_text = "I received your update and will review it shortly."
                  
             # Build SMTPConfig for current mailbox to send the reply back
             smtp_config = SMTPConfig(
                 smtp_host=record["smtp_host"],
                 smtp_port=record["smtp_port"],
                 sender_email=record["email"],
                 encrypted_password=record["encrypted_password"],
                 provider=record["provider"],
                 use_ssl=record["use_ssl"]
             )
             
             # Reply back using correct RFC-compliant thread matching headers
             subject_prefix = "" if thread_subject.lower().startswith("re:") else "Re: "
             reply_result = send_warmup_email(
                 config=smtp_config,
                 recipient=thread_sender,
                 subject=f"{subject_prefix}{thread_subject}",
                 body=reply_text,
                 in_reply_to=thread_msg_id,
                 references=thread_msg_id
             )
             replies_dispatched.append(reply_result["message_id"])
             
        logger.info(f"IMAP task finished. Rescued: {len(rescued)} | Replies sent: {len(replies_dispatched)}")
        return {"status": "success", "rescued_ids": rescued, "replies_sent": replies_dispatched}
        
    except (ConnectionError, TimeoutError) as conn_exc:
        retry_delay = self.default_retry_delay * (2 ** self.request.retries)
        logger.warning(f"Transient error encountered: {conn_exc}. Retrying task in {retry_delay}s...")
        raise self.retry(exc=conn_exc, countdown=retry_delay)
        
    except ValueError as auth_exc:
        logger.error(f"Permanent authentication error: {auth_exc}. Deactivating mailbox.")
        set_mailbox_inactive_in_db(mailbox_id, str(auth_exc))
        return {"status": "failed", "reason": "auth_failure", "error": str(auth_exc)}
        
    except Exception as e:
        logger.error(f"Unhandled exception during IMAP task: {e}")
        raise e
