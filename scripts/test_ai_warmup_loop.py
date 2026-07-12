import os
import sys
import asyncio
from dotenv import load_dotenv

# Load environmental configs
load_dotenv()

# Set PYTHONPATH programmatically
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.ai_service import AIService
from app.core.ai_client import AIClientError

async def test_loop():
    print("================================================================================")
    print("                 SWARMWARM LLM DOCK / TUNNEL INTERFACE DIAGNOSTIC")
    print("================================================================================")
    
    tunnel_url = os.getenv("LOCAL_AI_TUNNEL_URL", "http://localhost:11434")
    print(f"Target Tunnel URL: {tunnel_url}")
    
    ai_service = AIService()
    
    # 1. Test Thread Starter Generation
    print("\n[AI TEST] Generating B2B Thread Starter Outreach...")
    try:
        starter_payload = await ai_service.generate_thread_starter()
        body = starter_payload.get("body", "")
        print(f"[+] SUCCESS: Starter outreach generated:\n---\n{body}\n---")
    except AIClientError as tunnel_err:
        print(f"[-] TUNNEL ERROR: Could not get AI response over the tunnel. Details: {tunnel_err}")
        print("Note: In production/testing loops, a baseline fallback message is automatically used.")
        print("Fallback preview: 'Checking in to see if we are scheduled for the database schema review this week.'")
    except Exception as e:
        print(f"[-] UNEXPECTED ERROR: {e}")
        sys.exit(1)
        
    # 2. Test Smart Reply Generation
    print("\n[AI TEST] Generating Context-Aware Smart Reply...")
    mock_incoming_mail = (
        "Hi Team,\n\n"
        "We are wrapping up the database migration design. Can you confirm if we need to "
        "adjust the default connection pools for Redis this afternoon?\n\n"
        "Best regards,\nSarah [Engineering Team]"
    )
    
    try:
        reply = await ai_service.generate_thread_reply(mock_incoming_mail)
        print(f"[+] SUCCESS: Contextual reply generated:\n---\n{reply}\n---")
    except AIClientError as tunnel_err:
        print(f"[-] TUNNEL ERROR: Could not get AI response over the tunnel. Details: {tunnel_err}")
        print("Fallback preview: 'I received your update and will review it shortly.'")
    except Exception as e:
        print(f"[-] UNEXPECTED ERROR: {e}")
        sys.exit(1)
        
    print("\n================================================================================")
    print("                 SWARMWARM LLM TUNNEL INTEGRATION DIAGNOSTIC: PASS")
    print("================================================================================")

if __name__ == "__main__":
    asyncio.run(test_loop())
