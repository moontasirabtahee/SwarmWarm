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

## 🧱 Architecture

* **API / control plane:** FastAPI (`app/main.py`) — auth, mailbox fleet CRUD, billing, teams, analytics, SSE.
* **Database:** SQLAlchemy Core over `DATABASE_URL`. SQLite for local dev (auto-created + seeded); **PostgreSQL** for production, schema managed by **Alembic**.
* **Background workers:** Celery worker + Celery beat (nightly P2P allocation) over Redis.
* **Auth:** bcrypt password hashing, JWT access tokens + rotating refresh tokens, email verification, password reset, login rate limiting.
* **Billing:** plans / subscriptions with quota enforcement (mailbox ceiling + daily send cap); Stripe checkout + webhook (dev-mode fallback for local testing).
* **Teams:** organizations with members, roles, and email invitations.

---

## 🛠️ Local Installation

### 1. Environment
```bash
python -m venv venv
source venv/bin/activate            # Windows: .\venv\Scripts\activate
pip install -r requirements-dev.txt  # includes pytest; use requirements.txt for runtime only
cp .env.template .env                # then fill in SWARMWARM_SECRET_KEY + SWARMWARM_JWT_SECRET
```
Generate the two required secrets:
```bash
python -c "import os,base64;print('SWARMWARM_SECRET_KEY='+base64.b64encode(os.urandom(32)).decode())"
python -c "import secrets;print('SWARMWARM_JWT_SECRET='+secrets.token_urlsafe(48))"
```
Leaving `DATABASE_URL` unset uses a local SQLite file (auto-created and seeded with demo data on first boot).

### 2. Run
```bash
uvicorn app.main:app --reload                              # API + SPA on :8000
celery -A app.core.celery_app worker --loglevel=info       # background worker
celery -A app.core.celery_app beat --loglevel=info         # nightly scheduler
```

### 3. Test
```bash
pytest                                # full API + unit suite (isolated temp DB)
python scripts/test_crypto.py         # crypto diagnostic
```

---

## 🐳 Docker Compose (recommended for production)

Brings up Postgres + Redis + web + worker + beat, runs Alembic migrations automatically:
```bash
cp .env.template .env     # set SWARMWARM_SECRET_KEY and SWARMWARM_JWT_SECRET
docker compose up --build
```
The `web` container runs `alembic upgrade head` before serving. Health probes:
* Liveness: `GET /health`
* Readiness (checks DB): `GET /ready`

### Manual PostgreSQL deployment
```bash
export DATABASE_URL=postgresql+psycopg://user:pass@host:5432/swarmwarm
alembic upgrade head                                       # create/upgrade schema
uvicorn app.main:app --host 0.0.0.0 --port 8000
celery -A app.core.celery_app worker --loglevel=info
celery -A app.core.celery_app beat --loglevel=info
```

---

## 📊 Live Verification Console
* **Control Panel Portal:** `http://<HOST>:8000/`
* **Swagger API Endpoint Docs:** `http://<HOST>:8000/docs`

*Log in with your seeded administrator credentials to toggle between the Standard User view (placement rates, mailbox CRUD switches) and the Admin Radar telemetry dashboard (Redis queue backlog, token generation speeds, CPU temperature metrics).*
