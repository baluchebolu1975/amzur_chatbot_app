# Amzur Chatbot App

Amzur Chatbot App is a full-stack conversational AI platform with secure authentication, persistent chat threads, Google OAuth login, and streaming assistant responses.

## Highlights

- FastAPI backend with async SQLAlchemy and Alembic migrations
- React + TypeScript frontend powered by Vite and Tailwind CSS
- Email/password authentication with JWT stored in httpOnly cookie
- Google OAuth sign-in support
- Persistent chat threads and messages in PostgreSQL
- Streaming AI responses via Server-Sent Events (SSE)
- Thread CRUD support (create, list, rename, delete)
- Auto thread title generation from the first user message in a new chat

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

FRONTEND_ORIGIN=http://127.0.0.1:5173
COOKIE_NAME=amzur_access_token
ACCESS_TOKEN_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=480
```

### Frontend environment

Create file: frontend/.env

```env
VITE_API_BASE_URL=http://127.0.0.1:8000/api
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
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Backend health endpoint:

- GET http://127.0.0.1:8000/api/health

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

- POST /api/chat/threads                -> Create thread
- GET /api/chat/threads                 -> List user threads
- GET /api/chat/threads/{thread_id}     -> Fetch thread with messages
- PATCH /api/chat/threads/{thread_id}   -> Rename thread
- DELETE /api/chat/threads/{thread_id}  -> Delete thread

### Message APIs

- POST /api/chat/messages               -> Non-streaming response
- POST /api/chat/messages/stream        -> Streaming SSE response

### Auto title behavior

When a new thread still has a default title (for example New Chat), the first user message automatically updates the thread title based on that message subject.

## Runbook

### Quick start commands (Windows PowerShell)

```powershell
# Terminal 1: backend
cd backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

# Terminal 2: frontend
cd frontend
npm run dev
```

### Verify system

```powershell
# Backend health
python -c "import requests;print(requests.get('http://127.0.0.1:8000/api/health').status_code)"
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
