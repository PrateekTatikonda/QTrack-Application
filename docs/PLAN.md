# QTrack – Audit & Production-Readiness Plan

_Audit date: 2026-10-14_

This document records what was verified to work, what is broken or risky, and the phased plan to take QTrack to a production-grade codebase. Priority tags:

- **P0** – security issue or broken right now
- **P1** – functional bug / incorrect behaviour users will hit
- **P2** – robustness, scalability, maintainability
- **P3** – polish / developer experience

---

## 1. How the audit was done

| Check | Method | Result |
|---|---|---|
| Backend boots | `import app.main` with project venv | ❌ initially failed (`sse_starlette` missing) → ✅ after syncing venv to `requirements.txt` |
| Postgres | Live connection + `create_all` | ✅ connects, `queue_log` table OK |
| Redis | Port 6379 / Docker | ❌ not running (Docker Desktop engine stopped) |
| Queue endpoints | Real FastAPI app via `TestClient`, Redis swapped for in-memory `fakeredis` | ✅ logic works (details below) |
| Queue endpoints with Redis down | Live uvicorn + HTTP calls | ❌ raw 500 + stack trace; `/health-check` still says "working" |
| AI endpoints | Live `/ai/health`, `/ai/chat` against Groq | ✅ Groq connected, chat replies |
| Frontend type-check/build | `npm run build` | ❌ 7 TypeScript errors – no production build possible |
| Frontend lint | `npm run lint` | ❌ 12 errors, 3 warnings |

## 2. What works today

- FastAPI app starts (once dependencies are installed) and registers all routes.
- PostgreSQL logging of queue joins (`queue_log` table).
- Queue core flow against Redis: **join → live view → update status → remove** all return correct results.
- SSE live stream endpoint + Redis Streams publishing on join/update/remove.
- AI chat (`/ai/chat`) with Groq tool-calling; the `join_queue` tool reaches the real queue **only** when the server runs on `localhost:8000`.
- Frontend runs in Vite dev mode (dev mode does not type-check) with Join / Live Queue / Admin tabs and the AI assistant panel.

## 3. Issues found

### 3.1 Security (P0)

| # | Issue | Where |
|---|---|---|
| S1 | **Real Groq API key** in `backend/.env.example` (untracked, but would be pushed if added). **Rotate the key.** | `backend/.env.example` |
| S2 | **`backend/app/.env` (DB user/password) is tracked in git and pushed to GitHub.** Rotate DB password, untrack file, purge history (`git filter-repo`). | git history |
| S3 | Server logs print full `DB_URL` **including password** and the first 10 chars of the Groq key. _Fixed in Phase 1._ | `services/db.py`, `main.py`, `ai_agent.py` |
| S4 | CORS: `allow_origins=[..., "*"]` together with `allow_credentials=True`; SSE response also hard-codes `Access-Control-Allow-Origin: *`. | `main.py` |
| S5 | No authentication/authorization. Anyone can change status, remove patients, delete logs. | all write endpoints |
| S6 | WhatsApp webhook does not verify `X-Hub-Signature-256`; anyone can post fake messages that trigger AI + queue actions. | `app/api/routes/ai.py` |
| S7 | No rate limiting on `/ai/chat` (each call costs Groq tokens) or `/join-queue` (queue flooding). | API |
| S8 | Patient PII (name/phone) in Redis hashes with no TTL; AI conversations containing PII kept in process memory indefinitely. | Redis / `ai_agent.py` |

### 3.2 Broken right now (P0)

| # | Issue |
|---|---|
| B1 | Venv out of sync with `requirements.txt` (18 packages missing incl. `sse-starlette`) → backend would not start. _Fixed: fresh `backend/.venv` built from `requirements-dev.txt`._ |
| B2 | `npm run build` fails: missing `SpeechRecognition` types (not in TS 5.8 DOM lib), implicit `any`, unused imports. _Fixed in Phase 1._ |
| B3 | When Redis is down every queue endpoint throws an unhandled 500; `/health-check` doesn't check Redis or Postgres. |
| B4 | `docker-compose.yaml` only starts Redis; README claims it also starts PostgreSQL. |

### 3.3 Functional bugs (P1)

| # | Issue | Verified |
|---|---|---|
| F1 | **Service-name mismatch**: UI uses `ENT, CARDIO, ORTHO, NEURO, GENERAL` → queues `queue:cardio`, `queue:ortho`…; AI uses `cardiology, orthopedics, neurology…`. Patients booked via AI are **invisible** in the UI queue/admin view. | ✅ reproduced |
| F2 | "Branch" vs "Service" confusion: the UI *Branch* selector actually holds services and is sent as `branch_id`, so the backend stores `branch_id="CARDIO"`. | ✅ |
| F3 | AI tool `get_queue_status` calls `/queue-status`, which **does not exist** (404). | ✅ reproduced |
| F4 | AI tools `reschedule_appointment` and `cancel_appointment` are **mocks that report success** – the AI tells patients they're cancelled when nothing happened. `get_branch_info` returns hard-coded wait times. | code |
| F5 | AI agent calls its own API over HTTP at hard-coded `http://localhost:8000` – breaks on any other port/host; should call the service layer directly. | code |
| F6 | WhatsApp verification can never succeed: Meta sends `hub.mode` / `hub.verify_token` / `hub.challenge`; endpoint expects `hub_mode` etc. (no `alias`). | code |
| F7 | No validation: empty name/phone, `branch_id=""`, arbitrary status (`"banana"`) all accepted; the same phone can join the same queue repeatedly. | ✅ reproduced |
| F8 | Timestamps are naive UTC (`datetime.utcnow()`, no `Z`); browsers parse them as **local time**, so join times display off by the UTC offset (−5:30 in IST). | code |
| F9 | `/remove-log` `name` filter is a no-op (filters `user_id` twice). | code |
| F10 | Postgres log is never updated on status change/removal (`called_at`, `skipped` unused) – no audit trail or analytics possible. | code |
| F11 | `join-queue` writes Redis first, then Postgres; a DB failure leaves an orphan in Redis. | code |
| F12 | `cleanup_old_conversations` assumes `timestamp` is never `None`; per-session history grows unbounded (token cost rises every turn). | code |
| F13 | Spanish/Hindi system prompts omit the services list and branch-vs-service rules → tool calls in those languages are unreliable. | code |
| F14 | Frontend types declare `QueueResponse.branch_id`; backend returns `service_type`. | code |

### 3.4 Robustness & architecture (P2)

- 400-line `main.py` mixes config, routing, business logic, SSE and DB bootstrap; queue-enrichment logic copy-pasted **3×**; unused helper `get_current_queue_data`; two functions both named `root`; empty `api/queue.py`.
- Config loaded ad-hoc in 4 places from 2 different `.env` files; no typed settings object.
- `create_all()` at import time; no migrations (Alembic).
- Sync SQLAlchemy session inside `async` endpoints → blocks the event loop.
- Custom `SIGINT/SIGTERM` handlers call `sys.exit` and fight uvicorn's graceful shutdown.
- SSE: a blocking `XREAD` per client + full queue re-read with N `HGETALL`s per event (no pipelining). Streams never trimmed (`MAXLEN`) → unbounded growth.
- AI conversation state in a process-local dict → lost on restart, not shareable across workers.
- `print()` everywhere instead of structured logging.
- `requirements.txt` contains many unused packages (`huggingface_hub`, `hf-xet`, `typer`, `rich`, `tqdm`, `fsspec`…); no dev/test requirements.
- No automated tests; the `test_*.py` files are manual scripts ignored by git.
- Frontend: API URL hard-coded; duplicated types (`App.tsx` and `api.ts`); duplicated status/time helpers; `any` throughout; missing hook deps; toast spam on every SSE reconnect; AI assistant auto-speaks every reply.
- No Dockerfiles, no CI, no Python linter/formatter config.

### 3.5 Polish (P3)

_Root venv, frontend nesting, README and duplicate runner scripts were fixed in Phase 1._

- Repo root **is a Python venv** (`Lib/`, `Scripts/`, `Include/`, `pyvenv.cfg` mixed with source); `.vscode/settings.json` points at it.
- Frontend nested one level too deep (`frontend/qtrack-frontend/`) plus an empty stray `frontend/src/`; Vite template `README.md`, `react.svg`, title "Vite + React + TS" still present.
- README: duplicated architecture block, stray code fence, hard-coded `C:/Users/prate/...` paths, outdated project tree.
- Two near-identical runner scripts (`run_server.py`, `run_server_prod.py`).
- "Remove log" admin button uses a phone icon.

---

## 4. Target structure (Phase 1)

```
Qtrack-app/
├── backend/
│   ├── app/
│   │   ├── main.py               # app factory: middleware, lifespan, routers
│   │   ├── core/config.py        # single settings source (.env loading)
│   │   ├── api/
│   │   │   ├── deps.py           # shared dependencies (DB session)
│   │   │   └── routes/           # health.py, queue.py, ai.py
│   │   ├── db/session.py         # engine, SessionLocal, Base
│   │   ├── models/queue_log.py   # SQLAlchemy models
│   │   ├── schemas/              # Pydantic request/response models
│   │   └── services/             # redis_client, queue_service, ai_agent, whatsapp
│   ├── scripts/                  # reset_queue.py, smoke checks
│   ├── tests/                    # pytest suite (fakeredis + sqlite)
│   ├── requirements.txt
│   ├── requirements-dev.txt
│   ├── .env.example
│   └── run_server.py             # single runner (--reload flag)
├── frontend/                     # Vite project (flattened)
│   └── src/
│       ├── api/                  # client.ts, queue.ts, ai.ts
│       ├── config/env.ts         # VITE_API_BASE_URL
│       ├── features/             # queue/, admin/, ai-assistant/
│       ├── lib/                  # shared helpers (status colours, time format)
│       ├── types/                # shared TS types + speech API declarations
│       └── styles/
├── docs/PLAN.md
├── scripts/                      # start-backend.bat, start-frontend.bat
├── docker-compose.yml
└── README.md
```

## 5. Phased roadmap

### Phase 1 – Structure & hygiene (no behaviour change) ✅ **done**
- [x] Reorganise backend into the layered packages above; dedupe queue-read logic into `queue_service`.
- [x] Central `core/config.py`; single `backend/.env`; untrack `backend/app/.env`; scrub key from `.env.example`.
- [x] Move `create_all` into the app lifespan; drop custom signal handlers (runner now uses `timeout_graceful_shutdown` so Ctrl+C no longer hangs on open SSE connections).
- [x] Flatten frontend; split into `api/`, `types/`, `features/`, `lib/`; API URL from `VITE_API_BASE_URL`.
- [x] Fix TS build errors (speech type declarations, unused imports) → `npm run build` passes.
- [x] Characterisation tests for the queue API (pytest + fakeredis + SQLite) – 15 tests; the same HTTP tests also pass against the pre-refactor code.
- [x] Merge runner scripts (`run_server.py [--prod]`); move `.bat` launchers to `scripts/`; move compose file to root.
- [x] Relocate venv to `backend/.venv`; rewrite `.gitignore` (old `lib/` and `*.json` rules would have hidden source/config); update README & `.vscode`.
- [x] Stop logging secrets (DB URL with password, Groq key prefix) – S3.

Follow-ups left from Phase 1:
- An older, unused venv still exists at `backend/venv/` (gitignored) – delete when convenient.
- Changes are not committed yet. The untracking of `backend/app/.env` only takes effect once committed.

### Phase 2 – Security (P0) ← **next**
- [ ] Rotate Groq key + DB password; purge `.env` from git history.
- [ ] Strict CORS from config (no `*` with credentials; drop manual SSE CORS header).
- [ ] Admin auth (JWT or API key) for status/remove/log endpoints.
- [ ] WhatsApp signature verification + fix `hub.*` aliases.
- [ ] Rate limiting for `/ai/chat` and `/join-queue`.

### Phase 3 – Correctness (P1)
- [ ] Canonical services/branches registry (backend config → `/meta` endpoint → shared by UI and AI).
- [ ] Pydantic validation (non-empty name, phone format, status `Enum`); duplicate-join guard.
- [ ] Real `queue-status`, `cancel`, `reschedule` in `queue_service`; AI calls the service directly.
- [ ] Timezone-aware UTC timestamps (`datetime.now(UTC)`).
- [ ] Log status transitions & removals to Postgres.
- [ ] Fix `/remove-log` filter; atomic join (Redis transaction + compensation on DB failure).
- [ ] Graceful Redis/DB errors (503) and a real readiness check.

### Phase 4 – Robustness & scale (P2)
- [ ] Alembic migrations; async SQLAlchemy (`asyncpg`).
- [ ] Redis pipelining for queue reads; `XADD MAXLEN`; shared fan-out for SSE.
- [ ] Persist AI conversations in Redis with TTL + history window.
- [ ] Structured logging; trimmed `requirements.txt`; ruff + mypy; ESLint clean.
- [ ] Dockerfiles (backend, frontend/nginx), full compose (api, web, redis, postgres), GitHub Actions CI.

### Phase 5 – UX polish (P3)
- [ ] Routing (react-router) with separate patient / display / admin views; admin login.
- [ ] Patient "my token" status page; toast de-duplication; opt-in TTS.
- [ ] Proper branding, favicon, title; remove template assets.
