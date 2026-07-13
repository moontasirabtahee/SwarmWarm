import os
import sys
from dotenv import load_dotenv

# Load environmental configs
load_dotenv()

# Set PYTHONPATH programmatically
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.scheduler import generate_daily_swarm_graph, dispatch_daily_tasks
from app.core.db import list_all_mailboxes

def main():
    print("================================================================================")
    print("                 SWARMWARM CONCURRENT WORKFLOW INGRESS SIMULATOR")
    print("================================================================================")
    
    # Try querying mailbox nodes from the SQLite database first
    db_mailboxes = [m for m in list_all_mailboxes() if m["is_active"]]
    
    if db_mailboxes:
        print(f"Loaded {len(db_mailboxes)} active mailbox nodes from SQLite database:")
        for m in db_mailboxes:
            print(f" - ID: {m['id']} | Email: {m['email']} | User: {m['user_id']} | Provider: {m['provider']}")
        nodes_to_match = db_mailboxes
    else:
        # Fallback seeds
        print("[-] SQLite contains no mailboxes. Using seed simulation list:")
        mock_db_mailboxes = [
            {
                "id": "mailbox_google_1",
                "user_id": "user_1",
                "email": "abtahee@qoarc.com",
                "provider": "google",
                "is_active": True
            },
            {
                "id": "mailbox_microsoft_1",
                "user_id": "user_2",
                "email": "m.abtahee@brownmafia.com",
                "provider": "microsoft",
                "is_active": True
            },
            {
                "id": "mailbox_custom_1",
                "user_id": "user_3",
                "email": "node01@mabsj.com",
                "provider": "custom",
                "is_active": True
            },
            {
                "id": "mailbox_google_2",
                "user_id": "user_4",
                "email": "outreach@startup.net",
                "provider": "google",
                "is_active": True
            }
        ]
        for m in mock_db_mailboxes:
            print(f" - ID: {m['id']} | Email: {m['email']} | User: {m['user_id']} | Provider: {m['provider']}")
        nodes_to_match = mock_db_mailboxes
        
    try:
        # Calculate matching interactions
        matches = generate_daily_swarm_graph(nodes_to_match)
        
        print("\nCalculated Match Results:")
        for idx, match in enumerate(matches, 1):
             print(f" Match {idx}: {match['sender_email']} ---> {match['recipient_email']}")
             
        print("\nExecuting chronological task queue distribution...")
        dispatch_daily_tasks(matches)
        
        print("\n================================================================================")
        print("                 SWARMWARM WORKFLOW SIMULATION DISPATCH: SUCCESS")
        print("================================================================================")
        print("Tasks enqueued to Redis. Boot your Celery worker using:")
        print("  celery -A app.core.celery_app worker --loglevel=info")
        print("================================================================================")
        
    except Exception as e:
        print(f"\n[-] SIMULATION DISPATCH FAILED: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
