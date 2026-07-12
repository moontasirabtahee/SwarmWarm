# **Phase 3: Distributed Worker & Message Broker Architecture**

**Project:** SwarmWarm (Multi-Tenant P2P Email Warmup Engine)  
**Lead Engineer:** M. A. Moontasir Abtahee  
**Phase:** 3 (Distributed Concurrency & Asynchronous Task Scheduling Specification)  
**Status:** Protocol Integration Sign-off

---

## **1. Concurrency Architecture & State Telemetry Layout**

Phase 3 introduces asynchronous event driving and task distribution into the system blueprint. In a production multi-tenant framework, web servers (FastAPI) must never execute long-running socket connections directly (like authenticating to IMAP or waiting on SMTP network links). Doing so blocks the server thread pool, leading to connection timeouts for active dashboard users.  

Instead, our orchestrator shifts processing tasks to an asynchronous decoupled architecture using a message broker and execution workers.  

```plaintext
+-----------------------------------------------------------------------------------------+
|                                    PHASE 3 ARCHITECTURE TOPO                            |
|                                                                                         |
|  +--------------------+      +-------------------+       +---------------------------+  |
|  |   FastAPI App      | ---> |  Supabase DB Rows |  ---> |     Beat Scheduler        |  |
|  | (Triggers State)   |      | (Target Counts)   |       | (Nightly Graph Allocator) |  |
|  +--------------------+      +-------------------+       +---------------------------+  |
|           |                                                                |            |
|           v                                                                v            |
|  +--------------------+                                      +---------------------------+  |
|  | Redis Queue Engine | <----------------------------------- |   Scheduled Task Events   |  |
|  | (FIFO Task Broker) |                                      +---------------------------+  |
|  +--------------------+                                                                 |
|           |                                                                             |
|           +───────────────────────┬────────────────────────┐                            |
|           v                       v                        v                            |
|  +------------------+    +------------------+    +------------------+                   |
|  | Celery Worker 01 |    | Celery Worker 02 |    | Celery Worker 03 |                   |
|  |  (SMTP Engine)   |    |  (IMAP Engine)   |    |  (Local AI Sync) |                   |
|  +------------------+    +------------------+    +------------------+                   |
+-----------------------------------------------------------------------------------------+
```

---

## **2. Milestone Logic Flowcharts**

### **A. The Nightly Graph Allocation & Balancing Scheduler**

This logic governs the main scheduler event that fires every night to map out safe inter-tenant mailbox interactions for the next 24 hours without breaking cross-tenant isolation parameters.  

```plaintext
[ Trigger Event: Beat Clock Strikes 00:00 UTC ]  
                       │  
                       ▼  
[ Query Supabase for Active Mailbox Rows & Target Count Limits ]  
                       │  
                       ▼  
[ Group Mailboxes into Infrastructure Pools: Google, Microsoft, Custom ]  
                       │  
                       ▼  
[ Initialize Bipartite Graph Matching Loop ]  
                       │  
                       ├───> Constrain Check: Do mailboxes belong to the same Owner ID?  
                       │         ├─► YES ──► Reject Pair Allocation Loop  
                       │         └─► NO  ──► Proceed  
                       │  
                       ├───> Constrain Check: Have these domains matched within 48 Hours?  
                       │         ├─► YES ──► Re-shuffle Graph Node Matching  
                       │         └─► NO  ──► Proceed  
                       │  
                       ▼  
[ Save Allocation Tasks into Database Engine as "Pending Status Logs" ]
```

### **B. Asynchronous Message Broker Lifecycle with Fault Isolation**

This workflow charts how execution tasks pass through our Redis queue buffers and how the Celery sub-agents handle server-side errors, rate-limiting failures, or drops in connectivity.  

```plaintext
[ Read Pending Database Action Log ]  
                 │  
                 ▼  
[ Package Task Arguments into JSON Format ]  
                 │  
                 ▼  
[ Push Payload to Redis FIFO Storage Queue Container ]  
                 │  
                 ▼  
[ Idle Celery Worker Pulls Task off the Message Broker ]  
                 │  
                 ▼  
[ Execute Protocol Operation (SMTP Send or IMAP Spam Check) ]  
                 │  
                 ├───> Execution Matrix Result: SUCCESS?  
                 │         │  
                 │         ▼  
                 │   [ Update Supabase Log: Set Status to "Success" ]  
                 │   [ Increment Daily Sent Metric Count by +1 ]  
                 │  
                 └───► Execution Matrix Result: EXCEPTION / REJECTION?  
                           │  
                           ▼  
                     [ Inspect Error Footprint Trace ]  
                           │  
                           ├─► Rate Limit or Network Dropout?  
                           │         │  
                           │         ▼  
                           │   [ Trigger Retry Loop with Exponential Backoff ]  
                           │   [ Delay Re-execution to Broker Queue for 300s ]  
                           │  
                           └─► Hard Failure (Invalid Credential / Authentication Error)?  
                                     │  
                                     ▼  
                               [ Set Mailbox Active State flag to FALSE ]  
                               [ Record Error Log Payload to DB View Container ]  
                               [ Dispatch Dynamic Dashboard Alert Context ]
```

---

## **3. Text-Based Module Wireframes (Distributed Telemetry Monitor)**

These wireframes map the stdout logging views and queue data matrices required to visualize and debug the Phase 3 environment setup.

### **Module Wireframe 1: Redis Queue Payload Telemetry View (`redis-cli monitor`)**

```plaintext
================================================================================  
 SWARMWARM REDIS BROKER TRAFFIC MONITOR: ACTIVE RUNTIME TASK MEMORY  
================================================================================  
 [CHANNEL] queue:default | ACTIVE CONNECTIONS: 4 WORKERS  
   
 [POP PAYLOAD] Task-ID: d3b07384d-2a1c-4e89 | Status: EXECUTING  
 {  
   "task_name": "swarmwarm.worker.tasks.execute_smtp_send",  
   "args": {  
     "sender_log_id": "bd0182c1-a829-411a-821f",  
     "recipient_email": "receiver@swarmnode-b.org",  
     "injection_jitter_max": 180  
   },  
   "retries": 0,  
   "eta": "2026-07-12T20:45:12.110294Z"  
 }  
   
 [PUSH PAYLOAD] Task-ID: 7c8a192bc-71e3-b0c1 | Status: QUEUED  
 {  
   "task_name": "swarmwarm.worker.tasks.execute_imap_rescue",  
   "args": {  
     "target_mailbox_id": "c9284ba1-192a-441d-bb91",  
     "expected_message_id": "<20260712.202942.99120@swarmwarm.engine>"  
   },  
   "retries": 1,  
   "eta": "2026-07-12T20:50:00.000000Z"  
 }  
================================================================================
```

### **Module Wireframe 2: Celery Worker Diagnostic Cluster Standard Output (`celery -A swarmwarm.worker.celery_app worker`)**

```plaintext
================================================================================  
 SWARMWARM DISTRIBUTED EXECUTION NODES: RUNTIME ORCHESTRATION CLUSTER  
================================================================================  
 -------------- celery@swarmwarm-node-vps-01 v5.3.6 (Couchbase)  
 --- * *** ---   
 -- ******* --- OS: Linux-6.1.0-21-amd64-x86_64-with-glibc2.36  
 - *** * *** -- Broker: redis://112.90.12.44:6379/0  
 - ** * ** -- Results: disabled  
   
 [2026-07-12 20:42:51,110] [INFO] [MainProcess] Connected to redis://112.90.12.44:6379/0  
 [2026-07-12 20:42:51,118] [INFO] [MainProcess] celery@swarmwarm-node-vps-01: ready.  
   
 [TASK START] swarmwarm.worker.tasks.execute_smtp_send [d3b07384d-2a1c-4e89]  
 [DEBUG] Task-d3b0: Applied randomized sleep offset -> 114 seconds.  
 [DEBUG] Task-d3b0: Decrypting identity credentials block token for security verify... PASS.  
 [INFO]  Task-d3b0: Successfully logged into smtp.gmail.com on behalf of user account.  
 [TASK SUCCESS] swarmwarm.worker.tasks.execute_smtp_send [d3b07384d-2a1c-4e89]: "250 OK" in 116.42s  
   
 [TASK START] swarmwarm.worker.tasks.execute_imap_rescue [7c8a192bc-71e3-b0c1]  
 [WARN]  Task-7c8a: Target message not found in INBOX. Redirecting scan to SPAM folder...  
 [ALERT] Task-7c8a: Swarm communication element trapped in SPAM folder! Executing rescue...  
 [INFO]  Task-7c8a: Item copied to INBOX. Flags modified to (\Seen, \Important).  
 [TASK SUCCESS] swarmwarm.worker.tasks.execute_imap_rescue [7c8a192bc-71e3-b0c1]: "RESCUED" in 4.11s  
================================================================================
```

---

## **4. Verification & Phase Review**

Phase 3 structural architecture requirements are now fully locked into our engineering lifecycle. We have explicitly structured:

1. The backend graph-matching scheduler parameters for multi-tenant account protection.  
2. The queue architecture logic models using Redis message data paths.  
3. The handling strategies for faults, retries, and network errors inside our remote worker clusters.

With this structural specification entirely mapped out, Phase 3 design parameters are frozen.  

We are officially ready to proceed to **Phase 4: Local LLM Orchestration & Prompt Engineering**, where we will define the secure proxy topology and design the semantic structure for our AI text engine to run on your local hardware. Let me know when you are ready to explore Phase 4!
