# **Phase 1.5: Frontend UX Layout & Interface Wireframes**

Here is the complete **Frontend User Experience (UX) & Interface Design Specification Document** for *SwarmWarm*. This document outlines the complete structural path a user takes through the platform, mapped out page-by-page using clean, industrial text-based wireframes.

## **1. User Journey & Navigation Flow Chart**

The user follows a strict, secure path from onboarding to deep optimization analysis.  
```plaintext
                 [ Landing Page / Identity Gateway ]  
                                  │  
                                  ▼  
                    [ JWT Session Authentication ]  
                                  │  
                                  ▼  
                    [ Main Workspace Dashboard ]  
                     /            │            \  
                    /             │             \  
  [ + Onboard Mailbox ]   [ Fleet Analytics ]   [ System Audit Logs ]
```

## **2. Page-by-Page Comprehensive Wireframes**

### **Page 1: Identity & Gateway Access (/auth/login)**

* **UX Intent:** Clean, minimalist portal designed for quick authentication with strict validation states.

```plaintext
================================================================================  
 SWARMWARM | P2P SENDER REPUTATION MESH  
================================================================================  
   
   [ Authenticate Workspace Session ]  
     
   Identity Email:  
   [ abtahee@qoarc.com                                                ]  
     
   Security Password:  
   [ ********************************** ]  
     
   [ ] Keep this session authenticated for 7 days  
     
     
                 [ CREATE NEW PROFILE ]     [ INITIALIZE SIGN IN ]  
                   
 ------------------------------------------------------------------------------  
 System Alert Space:   
 [!] Always verify you are connecting via an encrypted TLS/HTTPS connection channel.  
================================================================================
```

### **Page 2: Central Fleet Workspace Dashboard (/dashboard)**

* **UX Intent:** The primary landing experience after logging in. It gives a broad macro-view of all linked assets, current daily scales, and macro telemetry trends.

```plaintext
================================================================================  
 SWARMWARM FLEET COMMAND                          [ Welcome, Abtahee ] [ Settings ]  
================================================================================  
 [Overview Workspace]    [+ Onboard Mailbox]    [System Logs]    [API Access]

 Collective Mesh Health: [ EXCELLENT ] | Active Swarm Node Count: [ 3 ]  
   
 Your Connected Mailbox Fleet  
 ------------------------------------------------------------------------------  
 IDENTIFIER                  TYPE        DAILY VOLUME   HEALTH SCORE   ACTION  
 ------------------------------------------------------------------------------  
 abtahee@qoarc.com           Google      [ 28 / 40 ]    [ 100% Clean ] [VIEW] [||]  
 m.abtahee@brownmafia.com    Microsoft   [ 14 / 50 ]    [ 1 Blacklist] [VIEW] [>]  
 node01@mabsj.com            Custom      [  4 / 30 ]    [ 100% Clean ] [VIEW] [||]  
 ------------------------------------------------------------------------------  
 [>] Resume Active Warmup  |  [||] Temporary Pause Task Cycle  
================================================================================
```

### **Page 3: Mailbox Provisioning Gateway (/dashboard/mailboxes/onboard)**

* **UX Intent:** Simplified infrastructure setup interface. It changes input properties depending on the provider chosen.

```plaintext
================================================================================  
 LINK NEW INTERACTION ENDPOINT TO THE SWARM                      [ <- Abort ]  
================================================================================  
   
 Choose Email Infrastructure Provider:  
  (*) Google Workspace      ( ) Microsoft 365      ( ) Custom IMAP/SMTP Server  
   
 ┌────────────────────────────────────────────────────────────────────────────┐  
 │ [!] NOTICE FOR GOOGLE USERS:                                               │  
 │ Do not use your primary master account login password. You must generate   │  
 │ and paste a 16-character 'App Password' from your Google Account Security. │  
 └────────────────────────────────────────────────────────────────────────────┘  
   
 Connection Parameters:  
  - Active Email Address: [ outreach@yourdomain.com                          ]  
  - Secure App Token:    [ *********************************************** ]  
    
 [X] Use default provider port connections (SMTP: 465, IMAP: 993)  
   
 Scaling Limits:  
  - Max Operational Target Ceiling: [ 40 ] emails / day  
   
                                 [ DISMISS ]   [ INITIALIZE HANDSHAKE & ONBOARD ]  
================================================================================
```

### **Page 4: Deep Mailbox Analytics & Ledger View (/dashboard/mailboxes/:id)**

* **UX Intent:** Deep individual node analysis screen. This is where the user tracks placement rates and monitors background activities.

```plaintext
================================================================================  
 NODE MONITOR | Identity: abtahee@qoarc.com                     [ <- Return ]  
================================================================================  
 Status: [ WARMING RUNNING ] | Provider: Google Workspace | Curve Day: 14 of 30  
   
 Target Daily Volume Scaling Matrix  
 [■■■■■■■■■■■■■■■■■■■■■■■■■■■■■─────] 28 / 40 Target Scale Limit reached today  
   
 Deliverability & Placement Split (Last 24 Hours)  
 ┌───────────────────────────────┐   Visual Metrics Distribution  
 │  INBOX PLACEMENT:   88%       │     
 │  SPAM PLACEMENT:    12%       │   INBOX: [████████████████████████░░░] 88%  
 │  SPAM RESCUES:      6 Nodes   │   SPAM:  [███░░░░░░░░░░░░░░░░░░░░░░░] 12%  
 └───────────────────────────────┘  
   
 Isolated Transaction Log Matrix (Real-Time Background Log Processing)  
 ------------------------------------------------------------------------------  
 TIMESTAMP (UTC)      EVENT ACTIONS       TARGET RECIPIENT       STATUS SCORE  
 ------------------------------------------------------------------------------  
 2026-07-12 20:45     SMTP_SEND           sales@brownmafia.com   [ SUCCESS ]  
 2026-07-12 20:50     IMAP_SPAM_RESCUE    node01@mabsj.com       [ RESCUED ]*  
 2026-07-12 21:02     AI_SMART_REPLY      outreach@startup.net   [ SUCCESS ]  
 ------------------------------------------------------------------------------  
 [*] Operational Note: This item landed in the spam folder; our system shifted  
     it back to the primary inbox and flagged it as 'Important' successfully.  
================================================================================
```

### **Page 5: Global System Audit Logs (/dashboard/logs)**

* **UX Intent:** Developer and systems engineer telemetry tool. It shows raw infrastructure events happening behind the dashboard across all background workers.

```plaintext
================================================================================  
 GLOBAL ARCHITECTURE SYSTEM AUDIT LOGS                           [ Clear Filter ]  
================================================================================  
 Filter logs: [ Show All Events ] [ Errors Only ] [ Network Tunnels ] [ AI Nodes ]  
   
 TIMESTAMP (UTC)      MODULE SOURCE       DIAGNOSTIC EVENT MASS TRACKER  
 ------------------------------------------------------------------------------  
 2026-07-12 20:38:12  CELERY_BEAT         Nightly P2P bipartite graph mapping complete.  
 2026-07-12 20:39:01  REDIS_BROKER        Enqueued 42 task items into FIFO channel buffer.  
 2026-07-12 20:41:14  LOCAL_AI_NODE       Gemma 4B compiled context tokens. (42 t/s)  
 2026-07-12 20:45:22  SMTP_WORKER_02      Connection block jitter offset applied: 47s.  
 2026-07-12 20:50:05  IMAP_WORKER_01      [RESCUE] Account abtahee@qoarc.com flag fix complete.  
 ------------------------------------------------------------------------------  
 Displaying 1-5 of 1529 events.                         [ First ] [ Prev ] [ Next ]  
================================================================================
```

## **3. Core UX Interaction Principles**

1. **Immediate Execution Feedback:** When a user updates connection options on Page 3, the backend doesn't save blindly. The frontend displays an active state spinner while the FastAPI backend runs a test SMTP/IMAP network check. The page only saves if the connection state returns Success.  
2. **Color-Coded Status Matrix:** While the wireframe layout is text-based, the interface implementation will use strict TailwindCSS design logic flags:  
   * [ SUCCESS ] and [ 100% Clean ] -> Deep Emerald Green (Conveys safety).  
   * [ RESCUED ] and [ PENDING ] -> Indigo Blue/Amber (Conveys ongoing system value).  
   * [ 1 Blacklist ] and [ ERROR ] -> Crimson Red (Conveys actionable warnings).
