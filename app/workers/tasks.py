import logging
import asyncio
from app.core.celery_app import app
from app.workers.smtp_engine import send_warmup_email, SMTPConfig
from app.workers.imap_engine import rescue_spam_emails, scan_unread_threads, IMAPConfig
from app.services.ai_service import AIService
from app.core.db import (
    get_mailbox_by_id,
    update_mailbox_active_state,
    create_interaction_log,
    create_system_log
)

logger = logging.getLogger("swarmwarm.tasks")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

def get_mailbox_record(mailbox_id: str) -> dict:
    """
    Retrieves mailbox parameters from the SQLite database.
    """
    record = get_mailbox_by_id(mailbox_id)
    if not record:
        raise ValueError(f"Mailbox record not found in database: {mailbox_id}")
    return record

def set_mailbox_inactive_in_db(mailbox_id: str, reason: str):
    """
    Disables an inactive mailbox in SQLite and logs a system audit event.
    """
    logger.error(f"[DATABASE UPDATE] Disabling mailbox {mailbox_id}. Reason: {reason}")
    update_mailbox_active_state(mailbox_id, False)
    create_system_log(
        module="CELERY_WORKER",
        event=f"Mailbox {mailbox_id} disabled. Reason: {reason}",
        level="ERROR"
    )

@app.task(bind=True, max_retries=3, default_retry_delay=300)
def execute_smtp_send_task(self, sender_mailbox_id: str, recipient_email: str):
    """
    Decoupled Celery task executing outbound secure SMTP dispatch with dynamic AI prompt starters.
    """
    logger.info(f"Starting SMTP send task. Sender ID: {sender_mailbox_id} | Recipient: {recipient_email}")
    create_system_log(
        module="SMTP_WORKER",
        event=f"Task start: SMTP send from {sender_mailbox_id} to {recipient_email}."
    )
    
    try:
        record = get_mailbox_record(sender_mailbox_id)
        if not record["is_active"]:
            logger.warning(f"Aborting SMTP task: Mailbox {sender_mailbox_id} is inactive.")
            return {"status": "skipped", "reason": "mailbox_inactive"}
            
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
        ai_used = False
        try:
             ai_payload = asyncio.run(ai_service.generate_thread_starter())
             body_text = ai_payload.get("body")
             if body_text:
                 ai_used = True
                 create_system_log(
                     module="LOCAL_AI_NODE",
                     event="Gemma 4B generated starter email context successfully."
                 )
             else:
                 body_text = ai_service.get_fallback_starter()
        except Exception as ai_err:
             logger.warning(f"Local AI inference tunnel failed: {ai_err}. Falling back to default baseline text.")
             body_text = ai_service.get_fallback_starter()
             create_system_log(
                 module="LOCAL_AI_NODE",
                 event=f"Local LLM failed ({ai_err}). Using template fallback.",
                 level="WARN"
             )
             
        # 2. Dispatch SMTP warmup using verified outbound module
        result = send_warmup_email(config, recipient_email, "Warmup Sync Request", body_text)
        
        # Write interaction log
        create_interaction_log(
            user_id=record["user_id"],
            mailbox_id=sender_mailbox_id,
            recipient_email=recipient_email,
            subject="Warmup Sync Request",
            action="sent",
            folder="INBOX",
            ai_replied=ai_used
        )
        
        create_system_log(
            module="SMTP_WORKER",
            event=f"Successfully sent warmup email from {record['email']} to {recipient_email}."
        )
        
        logger.info(f"SMTP send task completed successfully. Message-ID: {result['message_id']}")
        return {"status": "success", "message_id": result["message_id"]}
        
    except (ConnectionError, TimeoutError) as conn_exc:
        retry_delay = self.default_retry_delay * (2 ** self.request.retries)
        logger.warning(f"Transient error encountered: {conn_exc}. Retrying task in {retry_delay}s...")
        create_system_log(
            module="SMTP_WORKER",
            event=f"Transient network error: {conn_exc}. Retrying in {retry_delay}s.",
            level="WARN"
        )
        raise self.retry(exc=conn_exc, countdown=retry_delay)
        
    except ValueError as auth_exc:
        logger.error(f"Permanent authentication error: {auth_exc}. Deactivating mailbox.")
        set_mailbox_inactive_in_db(sender_mailbox_id, str(auth_exc))
        return {"status": "failed", "reason": "auth_failure", "error": str(auth_exc)}
        
    except Exception as e:
        logger.error(f"Unhandled exception during SMTP task: {e}")
        create_system_log(
            module="SMTP_WORKER",
            event=f"Unhandled exception: {e}",
            level="ERROR"
        )
        raise e

@app.task(bind=True, max_retries=3, default_retry_delay=300)
def execute_imap_rescue_task(self, mailbox_id: str, expected_message_id: str):
    """
    Decoupled Celery task executing inbound IMAP rescues, thread scanning,
    and context-aware AI threaded reply processing.
    """
    logger.info(f"Starting IMAP rescue task. Mailbox ID: {mailbox_id} | Expected Message-ID: {expected_message_id}")
    create_system_log(
        module="IMAP_WORKER",
        event=f"Task start: IMAP check for mailbox {mailbox_id}."
    )
    
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
        rescued = rescue_spam_emails(config, search_subject="Warmup")
        logger.info(f"IMAP rescue search completed. Rescued count: {len(rescued)}")
        
        for r_msg_id in rescued:
            create_interaction_log(
                user_id=record["user_id"],
                mailbox_id=mailbox_id,
                recipient_email=record["email"],
                subject="Warmup Sync Request (Rescued)",
                action="rescued",
                folder="Spam",
                ai_replied=False
            )
            create_system_log(
                module="IMAP_WORKER",
                event=f"[RESCUE] Rescued email {r_msg_id} from Spam folder for {record['email']}."
            )
        
        # 2. Scan Inbox for unread messages to reply to contextually
        logger.info("Scanning Inbox directory for incoming warmup thread loops...")
        unread_threads = scan_unread_threads(config, search_subject="Warmup")
        
        ai_service = AIService()
        replies_dispatched = []
        
        for thread in unread_threads:
             incoming_body = thread["body"]
             thread_msg_id = thread["message_id"]
             thread_sender = thread["sender_email"]
             thread_subject = thread["subject"]
             
             logger.info(f"Processing unread thread from: {thread_sender}...")
             
             # Generate smart reply
             ai_used = False
             try:
                  reply_text = asyncio.run(ai_service.generate_thread_reply(incoming_body))
                  if reply_text:
                       ai_used = True
                       create_system_log(
                           module="LOCAL_AI_NODE",
                           event=f"Gemma 4B generated contextual reply to {thread_sender}."
                       )
                  else:
                       reply_text = ai_service.get_fallback_reply()
             except Exception as ai_err:
                  logger.warning(f"AI Smart Reply generation failed: {ai_err}. Using generic confirmation template.")
                  reply_text = ai_service.get_fallback_reply()
                  create_system_log(
                      module="LOCAL_AI_NODE",
                      event=f"Failed to generate AI reply to {thread_sender}: {ai_err}. Using fallback.",
                      level="WARN"
                  )
                  
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
             
             # Record log
             create_interaction_log(
                 user_id=record["user_id"],
                 mailbox_id=mailbox_id,
                 recipient_email=thread_sender,
                 subject=f"{subject_prefix}{thread_subject}",
                 action="sent",
                 folder="INBOX",
                 ai_replied=ai_used
             )
             
             create_system_log(
                 module="IMAP_WORKER",
                 event=f"Dispatched reply from {record['email']} to {thread_sender}."
             )
             
        logger.info(f"IMAP task finished. Rescued: {len(rescued)} | Replies sent: {len(replies_dispatched)}")
        return {"status": "success", "rescued_ids": rescued, "replies_sent": replies_dispatched}
        
    except (ConnectionError, TimeoutError) as conn_exc:
        retry_delay = self.default_retry_delay * (2 ** self.request.retries)
        logger.warning(f"Transient error encountered: {conn_exc}. Retrying task in {retry_delay}s...")
        create_system_log(
            module="IMAP_WORKER",
            event=f"Transient network error: {conn_exc}. Retrying in {retry_delay}s.",
            level="WARN"
        )
        raise self.retry(exc=conn_exc, countdown=retry_delay)
        
    except ValueError as auth_exc:
        logger.error(f"Permanent authentication error: {auth_exc}. Deactivating mailbox.")
        set_mailbox_inactive_in_db(mailbox_id, str(auth_exc))
        return {"status": "failed", "reason": "auth_failure", "error": str(auth_exc)}
        
    except Exception as e:
        logger.error(f"Unhandled exception during IMAP task: {e}")
        create_system_log(
            module="IMAP_WORKER",
            event=f"Unhandled exception: {e}",
            level="ERROR"
        )
        raise e
