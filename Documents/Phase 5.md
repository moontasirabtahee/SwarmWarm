# **Phase 5: Dashboard API & Monitoring**

**Project:** SwarmWarm (Multi-Tenant P2P Email Warmup Engine)  
**Lead Engineer:** M. A. Moontasir Abtahee  
**Phase:** 5 (Dashboard API & Systems Telemetry Monitoring Specification)  
**Status:** Protocol Integration Sign-off

---

## **1. Executive Summary**

Phase 5 outlines the integration of the central Dashboard REST API and system-wide telemetry tracking metrics. Built on **FastAPI**, this layer connects the backend databases (Supabase), Celery schedulers, and worker clusters to the user interface, rendering real-time telemetry on sender reputation, mailbox health status, and P2P interaction counts.

---

## **2. FastAPI Endpoint Specifications**

The orchestration dashboard relies on a RESTful interface to manage fleets, check audit logs, and trigger handshakes, separating access privileges between **Standard User** and **Administrator** scopes.

### **Authentication Endpoints**
- `POST /api/v1/auth/login` - Authenticates user/admin sessions; issues JWT authorization bearer tokens with role payloads.
- `POST /api/v1/auth/register` - Registers new tenant accounts (defaults to standard `user` role).

### **Standard User Dashboard Endpoints**
*Note: All endpoints below are scoped and filtered strictly to the authenticated user's `user_id`.*
- `GET /api/v1/dashboard/stats` - Returns rolling warmup logs, placement metrics, and status indexes for the user's mailboxes.
- `GET /api/v1/mailboxes` - Retrieves details of all linked mailboxes under the active user's tenant context.
- `POST /api/v1/mailboxes/onboard` - Initiates connection handshake verification and adds a mailbox to the swarm.
- `GET /api/v1/mailboxes/{id}` - Returns historical statistics and rolling 24h metrics for a specific owned mailbox.
- `PATCH /api/v1/mailboxes/{id}/state` - Modifies runtime operational states (e.g., Active/Paused).
- `DELETE /api/v1/mailboxes/{id}` - Decouples mailbox asset from the P2P swarm and clears database associations.

### **Admin Dashboard Endpoints**
*Note: These endpoints require an authenticated user with `role = 'admin'`.*
- `GET /api/v1/admin/dashboard/stats` - Returns global cross-tenant telemetry (total sent volume, rescues, and active swarm node counts across all users).
- `GET /api/v1/admin/mailboxes` - Lists all connected mailboxes in the swarm across all tenants.
- `GET /api/v1/admin/users` - Lists all registered tenant accounts and their statuses.
- `GET /api/v1/admin/system/logs` - Queries global background cluster audit logs (Celery beat status, AI node queues, connection pools).

---

## **3. Telemetry Metrics Matrix**

To accurately capture Swarm Warmup metrics, background execution updates feed into the dashboard analytics tables.

### **Core Data Fields**
- **Dispatched Sends:** Rolling 24-hour total outbound SMTP events across linked endpoints.
- **Spam Interceptions / Rescues:** Count of IMAP scan events finding a swarm email inside the Spam/Junk folder and shifting it back to the Inbox.
- **AI Reply Activation Rate:** Percentage of outbound warmups executing personalized Gemma 4B local contextual replies.
- **Node Health Index:** Percentage status tracking blacklist entries, connection health status, and provider auth validity.

---

## **4. Verification & Diagnostics Checklist**

Before final showcase deploy, execute the following manual diagnostic endpoint verification tests:

| Target Component | Diagnostic Test Case | Expected Outcome |
| :--- | :--- | :--- |
| **Auth JWT Token** | Request endpoint with missing/expired authorization bearer | Returns `401 Unauthorized` status response code. |
| **Mailbox Status Patch** | Send payload `{"state": "PAUSED"}` to `/api/v1/mailboxes/{id}/state` | Node state shifts immediately; background worker skips processing for this ID. |
| **Telemetry Ingress** | Trigger Celery background task sequence -> Check `/api/v1/mailboxes/{id}` statistics | Rolling counts increment in realtime matching log timestamps. |
