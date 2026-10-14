# QTrack – Real-Time Hospital Queue Management

QTrack lets patients join hospital department queues (web UI or AI chat/WhatsApp), shows live queue state over Server-Sent Events, and gives staff an admin panel to call, complete or remove patients.

> Current status and the roadmap of known issues live in [docs/PLAN.md](docs/PLAN.md).

## Architecture

```
[React UI] ──HTTP/SSE──> [FastAPI] ──> [Redis: queues, patient hashes, streams]
[AI chat / WhatsApp] ──>     │
                             ├──> [PostgreSQL: queue_log]
                             └──> [Groq LLM: AI agent tool-calling]
```

## Tech stack

| Layer | Tech |
|---|---|
| Backend | Python 3.13, FastAPI, SQLAlchemy, redis-py (async), sse-starlette, Groq SDK |
| Frontend | React 18, TypeScript, Vite, axios, lucide-react |
| Data | Redis 7 (live queue + Streams), PostgreSQL (logging) |

## Project structure

```
Qtrack-app/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app factory (middleware, lifespan, routers)
│   │   ├── core/                # config.py (settings from .env), logging_config.py
│   │   ├── api/
│   │   │   ├── deps.py          # shared dependencies (DB session, Redis client)
│   │   │   └── routes/          # health.py, queue.py, ai.py
│   │   ├── db/session.py        # SQLAlchemy engine/session/Base
│   │   ├── models/              # ORM models (QueueLog)
│   │   ├── schemas/             # Pydantic request/response models
│   │   └── services/            # queue_service, ai_agent, redis_client, whatsapp, ai_suggestions
│   ├── scripts/                 # reset_queue.py, smoke/ (manual Groq/API checks)
│   ├── tests/                   # pytest suite (fakeredis + in-memory SQLite)
│   ├── requirements.txt         # runtime dependencies
│   ├── requirements-dev.txt     # + test tooling
│   ├── pyproject.toml           # project + pytest config
│   ├── .env.example             # copy to .env
│   └── run_server.py            # dev/prod runner
├── frontend/
│   └── src/
│       ├── api/                 # axios client, queue + AI endpoints, SSE
│       ├── config/env.ts        # VITE_API_BASE_URL
│       ├── features/            # queue/, admin/, ai-assistant/
│       ├── lib/                 # shared helpers
│       ├── types/               # shared TS types + Web Speech declarations
│       └── styles/
├── scripts/                     # start-backend.bat, start-frontend.bat
├── docs/PLAN.md                 # audit + roadmap
└── docker-compose.yml           # Redis
```

## Prerequisites

- Python 3.13+
- Node.js 18+
- PostgreSQL (local install) and Redis (via Docker, see below)

## Setup

### 1. Infrastructure

```bash
docker compose up -d          # starts Redis on :6379
```

PostgreSQL is expected to be running locally; create the database named in `DB_NAME`. Tables are created automatically on API startup.

### 2. Backend

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate   |   macOS/Linux: source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env          # then fill in real values
```

### 3. Frontend

```bash
cd frontend
npm install
cp .env.example .env.local    # optional: override VITE_API_BASE_URL
```

## Running

| What | Command (from repo root) |
|---|---|
| Backend, dev (auto-reload) | `cd backend && python run_server.py` |
| Backend, prod mode | `cd backend && python run_server.py --prod` |
| Frontend dev server | `cd frontend && npm run dev` |
| Windows shortcuts | `scripts\start-backend.bat [dev\|prod\|install]`, `scripts\start-frontend.bat` |

- Frontend: http://localhost:5173
- API: http://localhost:8000 — interactive docs at http://localhost:8000/docs

## Testing & checks

```bash
cd backend && python -m pytest          # API tests (no Redis/Postgres needed)
cd frontend && npm run build            # type-check + production build
cd frontend && npm run lint
```

Manual smoke checks against real services (from `backend/`):

```bash
python -m scripts.smoke.check_groq          # Groq key + model
python -m scripts.smoke.check_ai_agent      # end-to-end AI agent message
python -m scripts.smoke.check_join_queue    # POST /join-queue on a running server
python -m scripts.reset_queue ent           # clear a queue in Redis
```

## API overview

| Method | Path | Purpose |
|---|---|---|
| GET | `/health-check` | Liveness |
| POST | `/join-queue` | Add patient (`name`, `phone`, `branch_id`, `service_type`) |
| GET | `/live-queue/{service_type}` | Current queue |
| GET | `/live-queue-stream/{service_type}` | Live queue updates (SSE) |
| PUT | `/update-status` | Change patient status (`user_id`, `new_status`) |
| DELETE | `/remove-from-queue` | Remove patient (`branch_id`, `user_id`) |
| DELETE | `/remove-log` | Delete Postgres log entry (`user_id`) |
| POST | `/ai/chat` | Chat with the AI queue assistant |
| GET | `/ai/health` | Groq connectivity check |
| GET/POST | `/ai/whatsapp/webhook` | WhatsApp Business webhook |
| GET/DELETE | `/ai/conversation/{session_id}` | Read / clear AI conversation |

## Configuration

All backend settings come from `backend/.env` (see [backend/.env.example](backend/.env.example)) and are loaded in one place: `backend/app/core/config.py`.

| Variable | Purpose | Default |
|---|---|---|
| `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME` | PostgreSQL connection | – |
| `REDIS_HOST`, `REDIS_PORT`, `REDIS_PASSWORD` | Redis connection | `localhost`, `6379`, none |
| `CORS_ORIGINS` | Comma-separated allowed origins | localhost dev origins |
| `LOG_LEVEL` | Python log level | `INFO` |
| `GROQ_API_KEY`, `AI_MODEL` | AI agent | –, `qwen/qwen3.8-27b` |
| `MEDICAL_SERVICES` | Departments the AI may book | `general,emergency` |
| `INTERNAL_API_BASE_URL` | URL the AI agent uses to reach this API | `http://localhost:8000` |
| `WHATSAPP_*` | WhatsApp Business API | – |

Frontend: `VITE_API_BASE_URL` (default `http://localhost:8000`).

## Troubleshooting

- **Queue endpoints return 500** – Redis isn't running (`docker compose up -d`).
- **Startup fails connecting to Postgres** – check `DB_*` in `backend/.env` and that the database exists.
- **AI replies "limited mode"** – `GROQ_API_KEY` missing; run `python -m scripts.smoke.check_groq`.
