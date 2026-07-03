# Alma Lead Management — Design Document

> Status: DRAFT — written before implementation; will be updated as decisions firm up.

## 1. Problem

Alma (an immigration law firm) needs to capture prospective clients ("leads") from a
public form, notify both the prospect and an internal attorney by email, and give
attorneys an authenticated internal UI to review leads and mark them as contacted.

## 2. Requirements recap

**Functional**
- Public form: `first_name`, `last_name`, `email`, `resume/CV` (file upload). No auth.
- On submission: persist the lead, email the prospect (confirmation) and an attorney (notification).
- Internal UI (auth-guarded): list all leads with submitted info; each lead has a state.
- State machine: `PENDING` → `REACHED_OUT`, transitioned manually by an attorney. No other transitions.

**Technical**
- API: FastAPI. Web app: Next.js. Persistent storage. Real email-service integration.
- Production-style repo structure.

## 3. Architecture

```
┌─────────────────────────┐         ┌──────────────────────────┐
│  Next.js (frontend/)    │  HTTP   │  FastAPI (backend/)      │
│                         │────────▶│                          │
│  /            public    │  JSON / │  POST  /api/leads        │──▶ Postgres (leads)
│               lead form │  multi- │  GET   /api/leads   🔒   │──▶ File storage (resumes)
│  /admin       internal  │  part   │  PATCH /api/leads/{id} 🔒│──▶ Email service (async)
│               dashboard │         │  GET   /api/leads/{id}/resume 🔒
│  /admin/login           │         │  POST  /api/auth/login   │
└─────────────────────────┘         └──────────────────────────┘
```

Two apps in one monorepo. The Next.js app is presentation-only; all business logic,
validation, and the state machine live in the FastAPI service.

## 4. Data model

**Lead** (single table — deliberately no premature normalization)

| column            | type                              | notes                                   |
|-------------------|-----------------------------------|-----------------------------------------|
| id                | UUID, pk                          | server-generated                        |
| first_name        | text, required                    |                                         |
| last_name         | text, required                    |                                         |
| email             | text, required                    | validated (pydantic `EmailStr`)         |
| resume_path       | text, required                    | storage key, not a public URL           |
| resume_filename   | text, required                    | original name, for download             |
| resume_content_type | text, required                  | allowlist: pdf, doc, docx               |
| state             | enum `PENDING` / `REACHED_OUT`    | default `PENDING`                       |
| created_at        | timestamptz                       |                                         |
| updated_at        | timestamptz                       |                                         |
| reached_out_at    | timestamptz, nullable             | set on state transition                 |

State transitions are enforced server-side: the PATCH endpoint accepts only
`PENDING → REACHED_OUT`; anything else returns 409/422. (Idempotent re-marking: TBD —
lean toward 409 to keep the audit story clean.)

## 5. API contract

| Endpoint                        | Auth | Purpose                                              |
|---------------------------------|------|------------------------------------------------------|
| `POST /api/leads`               | none | Create lead. `multipart/form-data` (fields + file). Returns 201 + lead JSON (no resume path leaked). |
| `GET /api/leads`                | 🔒   | List leads, newest first. Pagination via `limit`/`offset`. |
| `GET /api/leads/{id}`           | 🔒   | Single lead detail.                                  |
| `PATCH /api/leads/{id}`         | 🔒   | Body: `{"state": "REACHED_OUT"}`. Only valid transition allowed. |
| `GET /api/leads/{id}/resume`    | 🔒   | Stream the resume file for attorney review.          |
| `POST /api/auth/login`          | none | Credentials → JWT for the internal UI.               |

Validation on `POST /api/leads`: email format, file required, content-type + extension
allowlist, max file size (5 MB). Errors are structured JSON the form can render inline.

## 6. Auth

Primary flow: **Google Sign-In (OAuth) with an email allowlist.**

1. The login page renders Google's Sign-In button (needs only a public OAuth client
   ID — no client secret, since we consume ID tokens, not access tokens).
2. The backend verifies the Google ID token (signature against Google's JWKS,
   audience, expiry, `email_verified`) and checks the email against
   `ADMIN_ALLOWED_EMAILS`; if allowlisted, it issues a short-lived app JWT.
3. The JWT is stored in a cookie so Next.js **middleware** can gate `/admin/*` routes
   (redirect to login when absent). The middleware is deliberately a UX gate only —
   every internal API endpoint (lead list, resume download, and the
   `PENDING → REACHED_OUT` state PATCH) independently verifies the JWT **and
   re-checks the allowlist on each request**, so delisting an email revokes access
   immediately even for unexpired tokens.

Fallback flow: env-configured credentials (`ADMIN_EMAIL`/`ADMIN_PASSWORD`) exchanged
for the same JWT — kept so reviewers can run the E2E demo without creating a Google
OAuth client. Disable in production by rotating the password.

*Production path (documented, not built):* per-attorney records with roles instead of
an env allowlist, HttpOnly session cookies via a BFF pattern, audit log of who marked
each lead.

## 7. Email flow

- Provider: **Resend** (simple API, generous free tier). Wrapped behind an
  `EmailService` interface with a **console/log fallback** so the app runs locally
  with zero API keys — the fallback prints the rendered email to stdout.
- Sender domain: `pactfulapp.com` — a domain I already owned from an unrelated side
  project, verified in Resend (DKIM/SPF) so delivery to *arbitrary* prospect
  addresses could be tested end-to-end. Resend's unverified sandbox sender only
  delivers to the account owner's inbox, which is fine for smoke tests but doesn't
  prove the real prospect-confirmation path. The domain is pure configuration
  (`EMAIL_FROM`); a production deployment would swap in the company domain.
- Two templates on lead creation:
  1. **Prospect confirmation** — "Thanks {first_name}, we received your information."
  2. **Attorney notification** — lead summary + link to the admin dashboard.
- Sent **after the DB commit**, via FastAPI `BackgroundTasks`: email failure must not
  fail the submission. Failures are logged.
- *Production path:* queue (SQS/Celery) with retries + dead-letter, delivery webhooks.

## 8. Storage

- **Database:** Postgres via `docker-compose` (SQLAlchemy 2.0 + Alembic migrations).
  Tests run against SQLite for speed. Object storage cannot replace this: lead rows
  are queried, listed, and state-transitioned — relational work.
- **Resumes:** S3-compatible object storage via boto3 — **MinIO** in docker-compose
  locally; moving to real AWS S3 is only an endpoint/credential change, no code.
  Behind the same `FileStorage` interface there is a local-disk fallback (used by
  tests and non-docker dev when `S3_ENDPOINT_URL` is unset). Files are served only
  through the authenticated download endpoint — never a public bucket or static path
  (resumes are PII).
- *Production path:* AWS S3 with presigned download URLs, bucket versioning +
  lifecycle rules.

## 9. Repo structure

```
.
├── README.md            # how to run locally (docker-compose up + seed steps)
├── DESIGN.md            # this document
├── NOTES.md             # running agent-usage / attribution log
├── AI_USAGE.md          # final ½-page agent-usage writeup (from NOTES.md)
├── docker-compose.yml   # postgres + backend + frontend
├── backend/
│   ├── app/
│   │   ├── main.py            # app factory, router mounting
│   │   ├── api/               # routers: leads.py, auth.py
│   │   ├── core/              # config (pydantic-settings), security
│   │   ├── models/            # SQLAlchemy models
│   │   ├── schemas/           # pydantic request/response schemas
│   │   ├── services/          # email.py, storage.py, leads.py (state machine)
│   │   └── db/                # session, Alembic migrations
│   ├── tests/
│   └── pyproject.toml
└── frontend/
    ├── app/
    │   ├── page.tsx           # public lead form
    │   ├── admin/page.tsx     # leads dashboard (guarded)
    │   └── admin/login/page.tsx
    ├── lib/api.ts             # typed API client
    └── components/
```

## 10. Key decisions & tradeoffs

| Decision | Choice | Why / alternative rejected |
|---|---|---|
| AI lead scoring | **Not built** | Not in requirements; the assignment evaluates agent *usage*, not AI features. 6-hour budget goes to required deliverables. Noted as future work. |
| DB | Postgres (docker) | "Production-level" signal; SQLite alone reads as toy. SQLite kept for tests. |
| Email | Resend + console fallback | Reviewer can run E2E without secrets; real integration still demonstrated. |
| Emails async? | BackgroundTasks, post-commit | Submission UX must not depend on the email provider; full queue is overkill here. |
| Auth | Google OAuth + email allowlist, JWT in cookie, Next middleware gate | Real OAuth without secrets (ID-token flow); allowlist re-checked per request server-side. Env-credential fallback kept so reviewers can run the demo with zero OAuth setup. |
| Resume storage | MinIO (S3 API) via boto3 | Same code path as production S3 — promoting to AWS is config-only. Local-disk fallback keeps tests and no-docker dev dependency-free. MinIO complements Postgres (files vs. queryable lead rows); it does not replace it. |
| Monorepo | Yes | One clone, one compose file, one README — reviewer friction matters. |

## 11. Out of scope / future work

- AI-assisted lead qualification (e.g., visa-fit summary from the CV)
- Multi-attorney routing / assignment, lead notes, richer state machine (e.g., `CLOSED`)
- Rate limiting / CAPTCHA on the public form (mention: it's a spam target)
- Delivery tracking for emails, S3 storage, real SSO
