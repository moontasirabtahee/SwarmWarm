import os
import sys
import time
import random

# Programmatically append project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.db import create_interaction_log, create_system_log

def simulate_worker_activity():
    print("================================================================================")
    print("                 SWARMWARM REAL-TIME TELEMETRY SIMULATOR")
    print("================================================================================")
    print("Press Ctrl+C to terminate simulation.")
    print("Injecting transactional log events into SQLite database every 3 seconds...")
    
    users = ["user_1", "user_2"]
    mailboxes = ["mailbox_google_1", "mailbox_microsoft_1"]
    actions = ["sent", "rescued"]
    
    count = 1
    try:
        while True:
            # Alternate user and mailbox configurations
            user = users[count % 2]
            mailbox = mailboxes[count % 2]
            action = actions[random.choice([0, 0, 1])] # 66% sends, 33% rescues
            ai_replied = random.choice([True, False])
            
            # Insert to SQLite DB log registry
            log_record = create_interaction_log(
                user_id=user,
                mailbox_id=mailbox,
                action=action,
                folder="INBOX" if action == "sent" else "Spam",
                ai_replied=ai_replied,
                subject="Warmup Sync Request",
                recipient_email=f"receiver-{count}@domain.com"
            )
            
            # Log corresponding background system audit events
            if action == "sent":
                module = f"SMTP_WORKER_0{random.randint(1,3)}"
                event = f"Successfully dispatched warmup email to receiver-{count}@domain.com"
                if ai_replied:
                    create_system_log(module="LOCAL_AI_NODE", event=f"Gemma 4B generated contextual text block for SMTP dispatch.")
                create_system_log(module=module, event=event)
            else:
                module = f"IMAP_WORKER_0{random.randint(1,3)}"
                event = f"[RESCUE] Swarm email flagged and moved to INBOX for {mailbox}."
                create_system_log(module=module, event=event)
            
            print(
                f"[SIMULATOR EVENT #{count}] Injected to SQLite -> "
                f"User: {user} | Mailbox: {mailbox} | Action: {action.upper()} | AI: {ai_replied}"
            )
            
            count += 1
            time.sleep(3.0)
            
    except KeyboardInterrupt:
        print("\n[SIMULATOR TERMINATED] Warmup simulation sequence stopped gracefully.")

if __name__ == "__main__":
    simulate_worker_activity()
