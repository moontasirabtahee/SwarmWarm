# SwarmWarm: Multi-Tenant P2P Email Warmup Engine

SwarmWarm is an industrial, production-grade peer-to-peer (P2P) email warmup control plane and background execution framework. It orchestrates automated SMTP/IMAP transactions across multi-tenant mailboxes, utilizing local LLM inference engines (Gemma 4B) over secure reverse-proxy tunnels to generate context-aware replies that bypass spam filters organically.

---

## 🚀 Key Features

* **Symmetric Credentials Encryption:** Production-grade AES-256-GCM byte encryption to safely lock mailbox credentials in persistent datastores.
* **Bipartite Interaction Scheduler:** Nightly allocation graph using `networkx` to calculate safe cross-tenant warmup pairs (enforcing strict domain isolation barriers).
* **Asynchronous Execution Queue:** Fault-tolerant Celery background tasks running over Redis message brokers with exponential backoff retry controls.
* **Semantic Smart Replies:** Integration with local LLM runtimes (Ollama/vLLM) to write human-like intro emails and replies, matching standard RFC threading headers (`In-Reply-To`, `References`).
* **Real-Time Telemetry Dashboard:** Responsive single-page application dashboard serving SSE live activity logs and telemetry grids for both standard Users and Infrastructure Admins.

---

## 📁 Repository Structure

```plaintext
SwarmWarm/
├── app/
│   ├── api/                    # REST routes (auth, CRUD fleet, analytics, SSE streams)
│   ├── core/                   # AES-GCM crypto, config parameters, database registry
│   ├── models/                 # Validation layers
│   ├── schemas/                # Pydantic serialization contracts
│   ├── services/               # LLM prompt adapters & bipartite scheduling algorithms
│   ├── static/                 # Frontend SPA (HTML, CSS, JS dashboard)
│   └── main.py                 # FastAPI application entrypoint
├── scripts/
│   ├── schema.sql              # Supabase PostgreSQL DDL configuration
│   ├── test_crypto.py          # Cryptography diagnostic checks
│   ├── test_smtp.py            # SMTP handshake dispatch validator
│   ├── test_imap.py            # IMAP scan and spam rescue validator
│   ├── test_ai_warmup_loop.py  # Async LLM proxy tunnel validator
│   ├── trigger_swarm_test.py   # Daily bipartite scheduler validator
│   └── run_e2e_warmup_simulation.py  # Real-time dashboard log simulator
├── requirements.txt            # Python dependencies manifest
└── .env.template               # Template environment configuration file
```

---

## 🛠️ Local Installation

### 1. Configure Python Virtual Environment
```bash
python -m venv venv
source venv/bin/activate  # On Windows: .\venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Set Up Local Configuration File
Copy the template and adjust your local environmental coordinates:
```bash
cp .env.template .env
```
Inside `.env`, configure:
* `SWARMWARM_SECRET_KEY`: A 32-byte base64-encoded master encryption key.
* `REDIS_BROKER_URL`: Connection string to your local Redis instance (`redis://localhost:6379/0`).

### 3. Run Diagnostic Verification Scripts
```bash
# Verify GCM Cryptography:
$env:PYTHONPATH="."; python scripts/test_crypto.py

# Verify LLM Tunnel Connectivity:
$env:PYTHONPATH="."; python scripts/test_ai_warmup_loop.py
```

---

## 🌐 Production VPS Deployment

### 1. Push Codebase Files to VPS
From your local terminal, copy the application structure to your cloud VPS:
```bash
ssh root@<VPS_IP> "mkdir -p /root/SwarmWarm"
scp -r app scripts requirements.txt .env.template root@<VPS_IP>:/root/SwarmWarm/
```

### 2. Configure VPS Prerequisites
SSH into your VPS and install dependencies:
```bash
apt update && apt upgrade -y
apt install python3 python3-pip python3-venv redis-server ufw -y

# Enable & start Redis broker
systemctl start redis-server && systemctl enable redis-server

# Allow gateway port 8000 and SSH through firewall
ufw allow OpenSSH
ufw allow 8000/tcp
ufw --force enable
```

### 3. Build VPS Runtime Environment
```bash
cd /root/SwarmWarm
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.template .env  # Edit and insert variables using nano
```

### 4. Launch Services in the Background
```bash
# Start FastAPI Server
nohup venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 > uvicorn.log 2>&1 &

# Start Celery Worker Node
PYTHONPATH=. nohup venv/bin/celery -A app.core.celery_app worker --loglevel=info > celery.log 2>&1 &
```

---

## 📊 Live Verification Console
* **Control Panel Portal:** `http://<VPS_IP>:8000/`
* **Swagger API Endpoint Docs:** `http://<VPS_IP>:8000/docs`

*Log in with your seeded administrator credentials to toggle between the Standard User view (placement rates, mailbox CRUD switches) and the Admin Radar telemetry dashboard (Redis queue backlog, token generation speeds, CPU temperature metrics).*
