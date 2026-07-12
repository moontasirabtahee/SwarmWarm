# **System Architecture & Technical Specifications Document**

**Project:** SwarmWarm (Multi-Tenant P2P Email Warmup Engine)  
**Lead Engineer:** M. A. Moontasir Abtahee  
**Phase:** 1 (Requirements, Architecture, Design Specification)  
**Status:** Approved for Core Prototyping

---

## **1. Executive Summary & Problem Space**

### **The Problem**

When an organization spins up brand-new domain identities for outbound communications, major Email Service Providers (ESPs) such as Google Workspace and Microsoft 365 view them with maximum structural suspicion. Immediately launching high-volume communications triggers automated anti-spam algorithms, leading to poor sender reputation, permanent domain blacklisting, and resource waste. Reversing this decay manually requires substantial operational overhead that cannot scale.

### **The Solution**

A centralized, multi-tenant software framework that establishes a collaborative Peer-to-Peer (P2P) reputation swarm. Multiple distinct users authenticate their unique mailboxes into a singular automated pool. The platform distributes interaction graphs across these cross-user endpoints to execute authentic human-emulation loops (sending, reading, spam rescuing, and deep conversational replies via a cost-free localized LLM microservice). This process systematically scales the domain trust footprint of the entire swarm.

---

## **2. Structural Requirements & System Topology**

### **A. Swarm Graph Allocation Principle**

To circumvent detection by behavioral spam models, an inbox must never send a transaction to itself, nor can accounts under the same user organization cluster execute tight loops. The system calculates a directed graph every 24 hours to generate the next day's tasks, balancing transactional paths evenly across distinct users and infrastructure providers (e.g., matching a Google node with a Microsoft node).

### **B. Automated Human Emulation (The Loop)**

* **Outbound Processing:** Asynchronous workers connect remotely to the sender's authenticated provider via secure **SMTP** to transmit unique business communications.  
* **Inbound & Spam Rescue:** Secondary workers log into the target recipient inbox using **IMAP**. The script audits the INBOX, Spam, and Junk folders. If an internal swarm email is located in a spam directory, the engine programmatically shifts it to the Primary Inbox, flag-tags it as Important, and sets the state to `\\Seen`.  
* **Contextual Threading:** The worker extracts the incoming text body, routes it to the AI microservice to generate an authentic response, and writes back using strict Message-ID and In-Reply-To SMTP header mapping to preserve email thread integrity.

### **C. Hybrid Infrastructure Topology**

```plaintext
+-------------------------------------------------------------------------------+
|                           CLOUD ARCHITECTURE (VPS)                            |
|                                                                               |
|   +--------------------+       +-------------------+       +--------------+   |
|   |  FastAPI Engine    | <---> |    Supabase DB    | <---> | Redis Broker |   |
|   |  (REST Gateway)    |       |  (State Engine)   |       | (Task Queue) |   |
|   +--------------------+       +-------------------+       +--------------+   |
|             ^                                                     |           |
|             | Secure Request                                      v           |
|             v                                              +--------------+   |
|   +--------------------+                                   | Celery Swarm |   |
|   | Cloudflare Tunnel  |                                   | (Workers)    |   |
|   +--------------------+                                   +--------------+   |
+-------------^-----------------------------------------------------|-----------+
              |                                                     |
              | Encrypted Proxy Relay                               | Remotely Dispatches
              v                                                     v Transactions
+------------------------------------+             +----------------------------+
|        LOCAL AI INFRASTRUCTURE     |             | THIRD-PARTY EMAIL NETWORKS |
|                                    |             |                            |
|    +--------------------------+    |             |    [ Google Workspace ]    |
|    | Local Inference Engine   |    |             |    [   Microsoft 365  ]    |
|    | (Gemma 4B Model Host)    |    |             |    [   Custom SMTP/IMAP]    |
|    +--------------------------+    |             |                            |
+------------------------------------+             +----------------------------+
```

---

## **3. System Data Model (Supabase PostgreSQL)**

```sql
-- Enforces referential integrity and strict tracking parameters across tenants  
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE users (  
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),  
    email VARCHAR(255) UNIQUE NOT NULL,  
    password_hash TEXT NOT NULL,  
    role VARCHAR(50) DEFAULT 'user' NOT NULL,  -- 'admin' or 'user'
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP  
);

CREATE TABLE mailboxes (  
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),  
    user_id UUID REFERENCES users(id) ON DELETE CASCADE NOT NULL,  
    email VARCHAR(255) UNIQUE NOT NULL,  
    smtp_host VARCHAR(255) NOT NULL,  
    smtp_port INT NOT NULL,  
    imap_host VARCHAR(255) NOT NULL,  
    imap_port INT NOT NULL,  
    encrypted_password TEXT NOT NULL,   
    provider VARCHAR(50) NOT NULL,    -- 'google', 'microsoft', 'custom'  
    daily_send_limit INT DEFAULT 40,  
    is_active BOOLEAN DEFAULT TRUE,  
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP  
);

CREATE TABLE warmup_schedules (  
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),  
    mailbox_id UUID REFERENCES mailboxes(id) ON DELETE CASCADE UNIQUE,  
    current_day_number INT DEFAULT 1,  
    target_send_count INT DEFAULT 2,  
    emails_sent_today INT DEFAULT 0,  
    is_cooling_down BOOLEAN DEFAULT FALSE,  
    last_processed_at TIMESTAMP WITH TIME ZONE,  
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP  
);

CREATE TABLE interaction_logs (  
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),  
    sender_mailbox_id UUID REFERENCES mailboxes(id) ON DELETE SET NULL,  
    recipient_mailbox_id UUID REFERENCES mailboxes(id) ON DELETE SET NULL,  
    message_id VARCHAR(255),  
    subject TEXT,  
    action_type VARCHAR(50) NOT NULL,      -- 'send', 'reply', 'spam_rescue'  
    status VARCHAR(50) DEFAULT 'pending',  -- 'pending', 'success', 'failed'  
    error_message TEXT,  
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP  
);
```

---

## **4. Text-Based Application Wireframes**

### **Wireframe 1: User Control Panel & Swarm Overview**

```plaintext
================================================================================  
 SWARMWARM SYSTEM CONTROLLER                      [ Welcome, Abtahee ] [ Logout ]  
================================================================================  
 [Overview Workspace]    [+ Onboard Mailbox]    [System Logs]    [API Access]

 Swarm Operational Fleet  
 ------------------------------------------------------------------------------  
 IDENTIFIER                  TYPE        RAMP INDEX     REPUTATION SCORE ACTION  
 ------------------------------------------------------------------------------  
 abtahee@qoarc.com           Google      [ 28 / 40 ]    [ 100% Nominal ] [Pause]  
 m.abtahee@brownmafia.com    Microsoft   [ 14 / 50 ]    [ 1 Blacklist  ] [Fix]  
 node01@mabsj.com            Custom      [  4 / 30 ]    [ 100% Nominal ] [Pause]  
 ------------------------------------------------------------------------------  
 System Operations Telemetry (Rolling 24 Hours)  
 Enqueued Sends: 42  |  Spam Interceptions: 6  |  LLM Synthesized Replies: 42  
================================================================================
```

### **Wireframe 2: Secure Mailbox Provisioning Interface (/mailboxes/onboard)**

```plaintext
================================================================================  
 LINK INTERACTION ENDPOINT TO THE SWARM                          [ <- Abort ]  
================================================================================  
 Infrastructure Target:  (*) Google Workspace  ( ) Microsoft 365  ( ) Custom IMAP  
   
 Encryption Gateway Parameters:  
  - Account Address:    [ outreach@yourdomain.com                     ]  
  - Secure App Token:   [ ******************************************** ]  
    
 Protocol Configurations (Auto-Provisioned for Tier-1 Providers):  
  - Outbound SMTP Host: [ smtp.gmail.com       ]   - Port Access: [ 465 ]  
  - Inbound IMAP Host:  [ imap.gmail.com       ]   - Port Access: [ 993 ]

 Scalability Controls:  
  - Max Operational Ceiling: [ 40 ] emails / day  
    
                                 [ DISMISS ]   [ INITIALIZE HANDSHAKE & SAVE ]  
================================================================================
```

---

## **5. Security & Isolation Specifications**

1. **Symmetric Crypto-Storage Layer:** Plaintext recording of SMTP/IMAP authentication secrets to the database is strictly forbidden. The service application layer must intercept raw application tokens, compress them using **AES-256-GCM**, and deposit the resulting ciphertext byte-string into Supabase. The single initialization vector and cryptographic decryption master key will exist strictly as an environmental variable inside the production VPS shell.  
2. **Network Connection Pooling:** To shield the VPS IP address from gatekeeper blocklists, background workers must wrap execution cycles inside dynamic connection pools. All outbound transactions will execute using randomized intervals (15 to 180 seconds of "jitter"), masking execution footprints completely.

---

## **Senior Engineering Verification**

Phase 1 requirements, architecture schemas, and structural constraints are now locked down and fully documented. This specification provides a comprehensive blueprint for your portfolio repository, demonstrating systematic systems design.  

We are now clearing our workspace for **Phase 2: Core Engine & Protocol Prototyping**. Our initial task will be building out our local environment and creating the cryptographic security wrapper script.  

Open up your terminal, initialize your project root folder, and let me know when you are ready to construct the encryption helper file.
