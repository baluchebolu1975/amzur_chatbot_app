# Amzur Chatbot App

[![Repo](https://img.shields.io/badge/repo-amzur_chatbot_app-0A66C2?logo=github)](https://github.com/baluchebolu1975/amzur_chatbot_app)
[![Python](https://img.shields.io/badge/python-3.12%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/backend-FastAPI-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/frontend-React%2019-61DAFB?logo=react&logoColor=black)](https://react.dev/)
[![Vite](https://img.shields.io/badge/bundler-Vite-646CFF?logo=vite&logoColor=white)](https://vitejs.dev/)
[![TypeScript](https://img.shields.io/badge/language-TypeScript-3178C6?logo=typescript&logoColor=white)](https://www.typescriptlang.org/)
[![Postgres](https://img.shields.io/badge/database-PostgreSQL-4169E1?logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Last Commit](https://img.shields.io/github/last-commit/baluchebolu1975/amzur_chatbot_app)](https://github.com/baluchebolu1975/amzur_chatbot_app/commits/main)

Amzur Chatbot App is a full-stack conversational AI platform with secure authentication, persistent chat threads, Google OAuth login, streaming assistant responses, and production-ready ticket triage integration with automated email notifications via n8n.

## Repo Landing Page

Production-ready internal chatbot platform focused on secure auth, persistent threads, and LiteLLM-routed AI responses.

### Quick Navigation

- [Highlights](#highlights)
- [Architecture Diagram](#architecture-diagram)
- [Local Setup](#local-setup)
- [Authentication Flow](#authentication-flow)
- [Chat Features](#chat-features)
- [Tickets Features (Project 13)](#tickets-features-project-13)
- [n8n Ticket Notifier Workflow](#n8n-ticket-notifier-workflow)
- [Smoke Test (Tickets + n8n)](#smoke-test-tickets--n8n)
- [Troubleshooting](#common-troubleshooting)

### Primary Entry Points

- Backend App: [backend/app/main.py](backend/app/main.py)
- API Routes: [backend/app/api/router.py](backend/app/api/router.py)
- Chat Service: [backend/app/services/chat_service.py](backend/app/services/chat_service.py)
- Tickets Route: [backend/app/api/routes/tickets.py](backend/app/api/routes/tickets.py)
- Ticket Schema: [backend/app/schemas/ticket.py](backend/app/schemas/ticket.py)
- n8n Tickets Service: [backend/app/services/n8n_service.py](backend/app/services/n8n_service.py)
- Frontend Bootstrap: [frontend/src/main.tsx](frontend/src/main.tsx)
- Chat Page: [frontend/src/pages/ChatPage.tsx](frontend/src/pages/ChatPage.tsx)
- Tickets Page: [frontend/src/pages/TicketsPage.tsx](frontend/src/pages/TicketsPage.tsx)

## Architecture Diagram

```mermaid
flowchart LR
	U[User Browser] --> FE[React + Vite Frontend]
	FE -->|HTTP + Cookie| API[FastAPI Backend]
	FE -->|Google OAuth| GOOG[Google Identity]
	GOOG -->|id_token| API

	API --> AUTH[Auth Service]
	API --> CHAT[Chat Service]
	AUTH --> SEC[JWT + bcrypt Security]
	CHAT --> DB[(PostgreSQL)]
	CHAT -->|streaming| SSE[SSE Response]

	CHAT --> LLM[LiteLLM Proxy]
	LLM --> MODEL[LLM Model]

	API --> ALEM[Alembic Migrations]
	ALEM --> DB
```

### Request Lifecycle (Chat)

1. User sends a prompt from frontend chat UI.
2. Frontend calls chat endpoint with auth cookie.
3. Backend validates JWT and resolves current user.
4. Chat service loads thread history from PostgreSQL.
5. For new threads, title auto-updates from first user message.
6. Prompt + history are sent to LiteLLM for model completion.
7. Tokens stream back via SSE and are persisted to database.
8. Frontend refreshes thread and message state.

## Highlights

- FastAPI backend with async SQLAlchemy and Alembic migrations
- React + TypeScript frontend powered by Vite and Tailwind CSS
- Email/password authentication with JWT stored in httpOnly cookie
- Google OAuth sign-in support
- Persistent chat threads and messages in PostgreSQL
- Streaming AI responses via Server-Sent Events (SSE)
- Thread CRUD support (create, list, rename, delete)
- Auto thread title generation from the first user message in a new chat
- Tickets tab in UI with create, list/history, and status update actions
- n8n sidecar integration for ticket triage and confirmation emails
- Supabase-backed ticket history rendering in the Tickets table

## Project Status (P1-P13)

- P1: Core full-stack scaffold (FastAPI + React + DB connectivity)
- P2: Authentication and session flow (email/password + cookie auth)
- P3: Chat threads, message persistence, and streaming chat responses
- P4: Memory window integration and conversation continuity controls
- P5: Attachment support with analysis for image/video/table/code/formula files
- P6: Image generation flow with base64 persistence in chat history
- P7: RAG document upload, indexing, and grounded document chat
- P8: DB Insights (natural language to SQL) with user-scoped safe query execution
- P9: Dataframe agent flow for structured sheet-style querying
- P10: Tic-Tac-Toe gameplay UI and backend route integration
- P11: LLM-powered Tic-Tac-Toe agent strategy with guarded fallback logic
- P12: MCP-based arXiv research integration via `mcp_simple_arxiv` with tool discovery and enforced clickable references
- P13: End-to-end ticket triage integration (FastAPI + n8n + Supabase + Tickets UI), including list/history, inline status update, DB-first persistence, DB fallback on n8n timeout, and automated Gmail email notifications via n8n Ticket Notifier workflow

### P12 MCP Integration Included

- Added MCP bridge service to connect backend chat flow with `mcp_simple_arxiv`
- Automatic MCP tool discovery for search/details (`search_papers`/`get_paper_data` with compatibility fallbacks)
- Research queries now receive MCP-grounded context before LLM generation
- Strict server-side reference hardening for clickable arXiv links in assistant responses
- No frontend UI contract changes required (plug-and-play tool backend swap)

### P8 Enhancements Included

- Dynamic schema discovery across public Supabase tables
- SQL validation and guardrails (SELECT-only + scoped filters)
- Thread-aware DB Insights queries
- Persisted DB Insights chat output containing:
  - Natural language answer
  - SQL query block
  - SQL result preview
- Frontend DB Insights result rendering in HTML table format

## Tech Stack

### Backend

- Python 3.12+
- FastAPI
- SQLAlchemy Async + asyncpg
- Alembic
- python-jose (JWT)
- bcrypt
- OpenAI SDK (via LiteLLM proxy)
- LangChain, LangGraph

### Frontend

- React 19
- TypeScript
- Vite
- Tailwind CSS
- TanStack Query
- Zustand
- Axios
- react-markdown + KaTeX support
- @react-oauth/google

## Repository Structure

```text
amzur-chatbot/
├─ backend/
│  ├─ app/
│  │  ├─ api/            # Routes, deps, API router
│  │  ├─ core/           # Settings, security helpers
│  │  ├─ db/             # DB base, session, Alembic env
│  │  ├─ models/         # SQLAlchemy ORM models
│  │  ├─ schemas/        # Pydantic request/response schemas
│  │  ├─ services/       # Business logic for auth/chat
│  │  ├─ ai/             # LLM setup and AI modules
│  │  └─ main.py         # FastAPI app entry point
│  ├─ alembic.ini
│  ├─ requirements.txt
│  └─ .env               # Local backend environment (not committed)
├─ frontend/
│  ├─ src/
│  │  ├─ components/     # Auth and chat UI components
│  │  ├─ hooks/          # React Query/Zustand hooks
│  │  ├─ lib/            # API client and query client
│  │  ├─ pages/          # Login and Chat pages
│  │  ├─ types/          # Zod schemas and TS types
│  │  └─ main.tsx
│  ├─ package.json
│  └─ .env               # Local frontend environment (not committed)
├─ CRUD_OPERATIONS.md
└─ README.md
```

## Prerequisites

- Python 3.12 or newer
- Node.js 20+ and npm
- PostgreSQL database (Supabase or local PostgreSQL)
- LiteLLM gateway credentials
- Google OAuth client credentials (optional, for Google sign-in)

## Environment Variables

Create the following files with your own values.

### Backend environment

Create file: backend/.env

```env
SECRET_KEY=replace_with_strong_secret
JWT_EXPIRE_MINUTES=480
APP_NAME=amzur-ai-chat
ENVIRONMENT=development

DATABASE_URL=postgresql+asyncpg://user:password@host:5432/dbname

LITELLM_PROXY_URL=https://litellm.amzur.com
LITELLM_API_KEY=replace_with_litellm_api_key
LLM_MODEL=gemini/gemini-2.5-flash
LITELLM_EMBEDDING_MODEL=text-embedding-3-large
IMAGE_GEN_MODEL=gemini/imagen-4.0-fast-generate-001

GOOGLE_CLIENT_ID=replace_with_google_client_id
GOOGLE_CLIENT_SECRET=replace_with_google_client_secret
GOOGLE_REDIRECT_URI=replace_with_redirect_uri_if_used

CHROMA_PERSIST_DIR=./chroma_db
GOOGLE_SERVICE_ACCOUNT_JSON=

MAX_UPLOAD_MB=20
UPLOAD_DIR=./uploads

N8N_WEBHOOK_URL=https://your-n8n-domain/webhook/tickets
N8N_STATUS_WEBHOOK_URL=https://your-n8n-domain/webhook/ticket-status
N8N_API_KEY=

FRONTEND_ORIGIN=http://127.0.0.1:5173
COOKIE_NAME=amzur_access_token
ACCESS_TOKEN_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=480
```

### Frontend environment

Create file: frontend/.env

```env
VITE_API_BASE_URL=http://127.0.0.1:8001/api
VITE_GOOGLE_CLIENT_ID=replace_with_google_client_id
```

## Local Setup

### 1) Backend setup

```bash
cd backend
python -m venv .venv
# Windows PowerShell
.\.venv\Scripts\Activate.ps1

pip install -r requirements.txt
```

### 2) Run migrations

```bash
cd backend
.\.venv\Scripts\Activate.ps1
alembic upgrade head
```

### 3) Start backend server

```bash
cd backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --host 127.0.0.1 --port 8001
```

Backend health endpoint:

- GET http://127.0.0.1:8001/api/health

### 4) Frontend setup

```bash
cd frontend
npm install
npm run dev
```

Frontend URL:

- http://127.0.0.1:5173

## Authentication Flow

### Email and password

- Register: POST /api/auth/register
- Login: POST /api/auth/login
- Session is stored in secure httpOnly cookie
- Logout: POST /api/auth/logout
- Current user: GET /api/auth/me

### Google OAuth

- Frontend obtains Google id_token
- Backend verifies token at POST /api/auth/google
- Backend issues the same JWT cookie model as email/password flow

Google Cloud setup must include authorized JavaScript origins such as:

- http://localhost:5173
- http://127.0.0.1:5173

## Chat Features

### Thread APIs

- POST /api/chat/threads -> Create thread
- GET /api/chat/threads -> List user threads
- GET /api/chat/threads/{thread_id} -> Fetch thread with messages
- PATCH /api/chat/threads/{thread_id} -> Rename thread
- DELETE /api/chat/threads/{thread_id} -> Delete thread

### Message APIs

- POST /api/chat/messages -> Non-streaming response
- POST /api/chat/messages/stream -> Streaming SSE response

### Auto title behavior

When a new thread still has a default title (for example New Chat), the first user message automatically updates the thread title based on that message subject.

## Tickets Features (Project 13)

### Tickets APIs

- POST /api/tickets -> Create a support ticket via n8n triage sidecar
- GET /api/tickets -> List ticket history for Tickets UI table
- PUT /api/tickets/{ticket_id}/status -> Update ticket status (Open/In Progress/Resolved/Closed)

### Tickets UI behavior

- Tickets tab is available in the main app layout alongside the Chatbot tab
- Create form supports: user_email, issue, category, priority
- My Tickets table renders persisted ticket history from Supabase
- Inline status editor updates ticket status from table rows
- Status changes are reflected immediately in the UI via React Query invalidation

### Ticket creation (resilient flow)

- Backend forwards payload to n8n Ticket Triage webhook (POST /webhook/tickets)
- n8n performs normalization, AI triage, and Supabase insert
- If n8n times out or is unavailable, backend falls back to a direct Supabase INSERT
- Ticket is never lost — either n8n or the fallback always persists the record
- Response includes ticket ID and creation timestamp

### Status update (DB-first flow)

- Backend writes status to Supabase FIRST with `UPDATE ... RETURNING id, category, priority, updated_at`
- DB commit succeeds before n8n is called — status is never lost on n8n timeout
- Enriched status payload (ticket_id, user_email, status, category, priority, updated_at) is forwarded to n8n Ticket Notifier webhook
- n8n Ticket Notifier sends a Gmail notification to the ticket owner

## n8n Ticket Notifier Workflow

### Workflow overview

- **Trigger**: Webhook node — POST `https://<your-n8n>/webhook/ticket-status`
- **Action**: Gmail node — sends an HTML email to the ticket owner on every status change
- **Response mode**: Immediately (async) — n8n returns HTTP 200 instantly without waiting for Gmail

### Gmail email template

The Gmail node expects these fields from the webhook body (all sent by the backend):

| Field | Source |
|---|---|
| `$json.body.ticket_id` | UUID from `tickets` table |
| `$json.body.status` | New status (Open / In Progress / Resolved / Closed) |
| `$json.body.user_email` | Ticket owner email |
| `$json.body.category` | Ticket category from DB |
| `$json.body.priority` | Ticket priority from DB |
| `$json.body.updated_at` | Timestamp of the status update |

> **Important**: Because the webhook uses async (Immediately) response mode, n8n wraps the POST body under `$json.body`. All Gmail template expressions must use `{{ $json.body.field_name }}` not `{{ $json.field_name }}`.

### Recommended Gmail message body (HTML)

```html
<h2>Your Ticket Has Been Updated</h2>
<p><b>Ticket ID:</b> {{ $json.body.ticket_id }}</p>
<p><b>Status:</b> {{ $json.body.status }}</p>
<p><b>Category:</b> {{ $json.body.category }}</p>
<p><b>Priority:</b> {{ $json.body.priority }}</p>
<p><b>Updated At:</b> {{ $json.body.updated_at }}</p>
```

### n8n environment variables required

```env
N8N_WEBHOOK_URL=https://your-n8n-domain/webhook/tickets
N8N_STATUS_WEBHOOK_URL=https://your-n8n-domain/webhook/ticket-status
```

## Smoke Test (Tickets + n8n)

Use the integration smoke script to validate health, ticket creation, direct webhook behavior, and response formatting.

```bash
cd backend
.\.venv\Scripts\Activate.ps1
python smoke_test_integration.py
```

Expected scope:

- Backend health endpoint is reachable
- Ticket creation endpoint returns HTTP 201 for valid payloads
- n8n webhook responds with required fields
- Tickets are persisted and visible in Tickets UI

## Runbook

### Quick start commands (Windows PowerShell)

```powershell
# Terminal 1: backend
cd backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --host 127.0.0.1 --port 8001

# Terminal 2: frontend
cd frontend
npm run dev
```

### Verify system

```powershell
# Backend health
python -c "import requests;print(requests.get('http://127.0.0.1:8001/api/health').status_code)"
```

Expected output: 200

## Testing

Backend test dependencies are included. If tests are present:

```bash
cd backend
.\.venv\Scripts\Activate.ps1
pytest -q
```

Frontend test scripts can be added as the suite evolves.

## Security Notes

- Never commit .env files
- Keep JWT secret strong and private
- Use secure=true cookies in non-development environments
- Restrict CORS origins in production
- Rotate API keys and OAuth secrets periodically

## Common Troubleshooting

### Port already in use (8000 or 5173)

Use netstat to find process and terminate if needed:

```powershell
netstat -ano | findstr ":8000"
taskkill /PID <pid> /F
```

### Google OAuth origin_mismatch

Add all local origins to Google Cloud OAuth authorized JavaScript origins.

### Registration fails with conflict

Email already exists. Use login instead, or register with a different email.

### CORS issues

Confirm FRONTEND_ORIGIN and allow_origins include the exact frontend host and port.

## Deployment Guidance

- Set ENVIRONMENT=production
- Use HTTPS and secure cookies
- Configure production CORS origins only
- Use managed Postgres and secret manager
- Add CI checks for lint, build, and tests
- Add observability (structured logs, metrics, tracing)

## License

No license file is currently included. Add one if this repo will be shared beyond internal use.
