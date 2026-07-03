# Alma Lead Management

A take-home exercise for Alma: a public lead-capture form for immigration prospects,
email notifications on submission, and an auth-guarded internal dashboard where
attorneys review leads and mark them as reached out.

- **Backend:** FastAPI · SQLAlchemy 2.0 · Alembic · Postgres
- **Frontend:** Next.js (App Router, TypeScript)
- **Email:** Resend (with a zero-config console fallback)
- **Resume storage:** MinIO (S3-compatible, via boto3 — swaps to AWS S3 with config only)

📄 [DESIGN.md](DESIGN.md) — architecture and design decisions ·
[NOTES.md](NOTES.md) — running agent-usage log · [AI_USAGE.md](AI_USAGE.md) — agent-usage writeup

## Quick start (Docker)

Requires Docker with Compose.

```bash
docker compose up --build
```

Then:

| URL | What |
|---|---|
| http://localhost:3000 | Public lead form |
| http://localhost:3000/admin | Attorney dashboard (fallback login: `attorney@example.com` / `Password1234!`; Google Sign-In when configured — see below) |
| http://localhost:8000/docs | API docs (OpenAPI) |
| http://localhost:9001 | MinIO console (login: `alma` / `alma-minio-secret`) — browse the `resumes` bucket |

**Email:** by default no external service is needed — submission emails are rendered to
the backend logs (`docker compose logs -f backend`). To send real email through Resend:

```bash
RESEND_API_KEY=re_xxx ATTORNEY_NOTIFICATION_EMAIL=you@example.com docker compose up --build
```

> Note: with Resend's sandbox sender (`onboarding@resend.dev`), Resend only delivers to
> the email address that owns the API key. Verify a domain to send to anyone.

The E2E flow to demo: submit the form at `:3000` → see both emails in the backend logs
(or your inbox) → sign in at `/admin` → download the resume → **Mark reached out** →
state flips `PENDING → REACHED_OUT`.

### Google Sign-In (optional)

The primary admin login is Google OAuth restricted to an email allowlist; the
credential login above is a zero-setup fallback. To enable Google:

1. In [Google Cloud Console](https://console.cloud.google.com/apis/credentials),
   create an **OAuth client ID** (type: Web application) with
   `http://localhost:3000` as an authorized JavaScript origin. No client secret is
   needed — the app consumes ID tokens only.
2. Start the stack with the client ID and your allowlist:

```bash
GOOGLE_CLIENT_ID=xxx.apps.googleusercontent.com \
ADMIN_ALLOWED_EMAILS=you@gmail.com,colleague@gmail.com \
docker compose up --build
```

The same `GOOGLE_CLIENT_ID` value feeds the backend (token verification) and the
frontend build (the Sign-In button). Non-allowlisted Google accounts get a 403, and
the allowlist is re-checked on every API request — removing an email locks that
account out immediately, even with an unexpired token.

## Running without Docker

**Backend** (needs Python 3.12+ and a running Postgres — or use
`docker compose up db` for just the database):

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env        # defaults point at localhost:5432
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

**Frontend:**

```bash
cd frontend
npm install
npm run dev                 # http://localhost:3000, API assumed at :8000
```

## Tests

```bash
cd backend
pytest
```

Tests run against in-memory SQLite with a recording email fake — no services needed.
(E2E tests are excluded from the default run; see below.)

With the Docker stack running, two suites test the real thing end to end:

```bash
cd backend && pytest -m e2e        # API contract: submission → auth → resume roundtrip through MinIO → state machine
cd frontend && npx playwright test # browser journeys: lead form → login → dashboard → mark reached out
```

`scripts/e2e.sh` runs both. Submission emails land in the backend logs
(`docker compose logs backend | grep "console email"`).

## Configuration

All backend settings come from environment variables (see `backend/.env.example`):
`DATABASE_URL`, `JWT_SECRET`, `GOOGLE_CLIENT_ID` / `ADMIN_ALLOWED_EMAILS` (Google
admin login), `ADMIN_EMAIL` / `ADMIN_PASSWORD` (fallback dashboard login),
`RESEND_API_KEY` (empty = console fallback), `EMAIL_FROM`,
`ATTORNEY_NOTIFICATION_EMAIL`, `FRONTEND_ORIGIN`, `S3_ENDPOINT_URL` /
`S3_BUCKET` / `S3_ACCESS_KEY` / `S3_SECRET_KEY` (empty endpoint = local-disk
fallback at `UPLOAD_DIR`).

To point at real AWS S3 instead of MinIO: set `S3_ENDPOINT_URL` to the AWS endpoint
(or adapt the client to default credentials), plus your bucket and IAM keys — the
application code is identical.

## Project layout

```
backend/
  app/
    api/routes/    # HTTP layer: leads.py (public form + internal), auth.py
    core/          # settings, JWT auth
    db/            # engine/session, Alembic migrations
    models/        # SQLAlchemy models (Lead + state enum)
    schemas/       # pydantic request/response models
    services/      # business logic: leads (state machine), email, storage
  tests/           # API tests (SQLite + email fake)
frontend/
  app/             # / (public form), /admin (dashboard), /admin/login
  lib/api.ts       # typed API client
docker-compose.yml # postgres + backend + frontend
```
