import os
import sys
import time
import random
from datetime import datetime

# Programmatically append project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.db import INTERACTION_LOGS

def simulate_worker_activity():
    print("================================================================================")
    print("                 SWARMWARM REAL-TIME TELEMETRY SIMULATOR")
    print("================================================================================")
    print("Press Ctrl+C to terminate simulation.")
    print("Injecting transactional log events into database registry every 3 seconds...")
    
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
            
            # Setup mock database log dictionary
            log_record = {
                "user_id": user,
                "mailbox_id": mailbox,
                "action": action,
                "folder": "INBOX" if action == "sent" else "Spam",
                "ai_replied": ai_replied,
                "created_at": datetime.utcnow().isoformat() + "Z"
            }
            
            # Insert to shared DB log registry
            INTERACTION_LOGS.append(log_record)
            
            print(
                f"[SIMULATOR EVENT #{count}] Injecting -> "
                f"User: {user} | Mailbox: {mailbox} | Action: {action.upper()} | AI: {ai_replied}"
            )
            
            count += 1
            time.sleep(3.0)
            
    except KeyboardInterrupt:
        print("\n[SIMULATOR TERMINATED] Warmup simulation sequence stopped gracefully.")

if __name__ == "__main__":
    simulate_worker_activity()
