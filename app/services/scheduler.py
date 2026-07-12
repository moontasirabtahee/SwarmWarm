import logging
import random
import networkx as nx
from app.workers.tasks import execute_smtp_send_task, execute_imap_rescue_task

logger = logging.getLogger("swarmwarm.scheduler")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

def generate_daily_swarm_graph(mailboxes: list, history_matches: set = None) -> list:
    """
    Executes bipartite graph matching calculations to generate safe P2P pairs.
    Enforces multi-tenant isolation shields and minimizes duplicate matches.
    """
    logger.info("Starting daily P2P swarm graph allocation calculation...")
    
    if history_matches is None:
        history_matches = set()
        
    G = nx.DiGraph()
    
    # Active nodes only
    senders = [m for m in mailboxes if m.get("is_active", True)]
    recipients = [m for m in mailboxes if m.get("is_active", True)]
    
    for s in senders:
        G.add_node(s["email"], bipartite=0, data=s)
    for r in recipients:
        G.add_node(r["email"], bipartite=1, data=r)
        
    for s in senders:
        for r in recipients:
            # Multi-Tenant Shield Assertion: Enforce absolute data boundaries
            # A node must never email a mailbox belonging to its same owner ID
            if s["user_id"] == r["user_id"]:
                continue
                
            # Block self-sending and root domain matches
            if s["email"] == r["email"]:
                continue
            
            s_domain = s["email"].split('@')[-1]
            r_domain = r["email"].split('@')[-1]
            if s_domain == r_domain:
                continue
                
            # Rolling 48-hour matching history validation
            if (s["email"], r["email"]) in history_matches:
                continue
                
            # Prioritize cross-provider interactions (boost weight)
            weight = 1.0
            if s["provider"] != r["provider"]:
                weight = 1.5
                
            G.add_edge(s["email"], r["email"], weight=weight)
            
    matches = []
    random.shuffle(senders)
    received_counts = {r["email"]: 0 for r in recipients}
    
    for s in senders:
        valid_targets = list(G.successors(s["email"]))
        if not valid_targets:
            continue
            
        # Prioritize matching based on received counts and provider weights
        valid_targets.sort(key=lambda r_email: (received_counts[r_email], -G.edges[s["email"], r_email]["weight"]))
        target_email = valid_targets[0]
        
        # Limit mailbox overload
        if received_counts[target_email] < 5:
            sender_node = s
            recipient_node = next(r for r in recipients if r["email"] == target_email)
            
            # Explicit Multi-Tenant Shield Validation assertion check (Task 3.2.2)
            assert sender_node["user_id"] != recipient_node["user_id"], \
                f"Multi-Tenant Shield Violated: {sender_node['email']} and {recipient_node['email']} share user_id {sender_node['user_id']}"
                
            matches.append({
                "sender_id": sender_node.get("id", sender_node["email"]),
                "recipient_id": recipient_node.get("id", recipient_node["email"]),
                "sender_email": sender_node["email"],
                "recipient_email": recipient_node["email"]
            })
            received_counts[target_email] += 1
            
    logger.info(f"Bipartite graph matches calculated. Total pairs: {len(matches)}")
    return matches

def dispatch_daily_tasks(matches: list):
    """
    Distributes allocated matching tasks chronologically over standard corporate hours.
    Injects individual execution triggers smoothly across the timeline.
    """
    logger.info(f"Preparing to dispatch {len(matches)} pairs smoothly across corporate hours...")
    
    # Define standard corporate hours interval (e.g. 8 hours = 28800 seconds)
    total_segment_seconds = 8 * 3600
    
    for idx, match in enumerate(matches):
        # Calculate segmented delay offset (smooth distribution)
        delay_offset = int((total_segment_seconds / len(matches)) * idx)
        
        # We also add a small randomized jitter to keep execution organic
        jitter = random.randint(10, 120)
        task_delay = delay_offset + jitter
        
        logger.info(
            f"Scheduling Pair: {match['sender_email']} -> {match['recipient_email']} "
            f"| Countdown: {task_delay}s (~{task_delay // 60}m offset)"
        )
        
        # Dispatch SMTP Outbound Task with Celery countdown
        execute_smtp_send_task.apply_async(
            args=[match["sender_id"], match["recipient_email"]],
            countdown=task_delay
        )
        
        # Dispatch IMAP Spam Rescue Task with a matching offset (e.g., runs 15 minutes after SMTP)
        execute_imap_rescue_task.apply_async(
            args=[match["recipient_id"], f"<warmup-{match['sender_id']}>"],
            countdown=task_delay + 900
        )
        
    logger.info("All daily warmup tasks successfully enqueued to Celery broker.")
