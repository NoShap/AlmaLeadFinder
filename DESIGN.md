# Alma Lead Management — Design Document

> Status: LIVING — originally drafted before implementation, since updated to match
> what was built (auth, deletion, and the three-layer test strategy in §9).

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
│               dashboard │         │  DELETE /api/leads/{id} 🔒
│  /admin/login           │         │  GET   /api/leads/{id}/resume 🔒
│                         │         │  POST  /api/auth/login   │
│                         │         │  POST  /api/auth/google  │
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
| email             | text, required, **unique**        | validated (pydantic `EmailStr`), stored lowercase — one lead per prospect email |
| resume_path       | text, required                    | storage key, not a public URL           |
| resume_filename   | text, required                    | original name, for download             |
| resume_content_type | text, required                  | allowlist: pdf, doc, docx               |
| state             | enum `PENDING` / `REACHED_OUT`    | default `PENDING`                       |
| created_at        | timestamptz                       |                                         |
| updated_at        | timestamptz                       |                                         |
| reached_out_at    | timestamptz, nullable             | set on state transition                 |

State transitions are enforced server-side: the PATCH endpoint accepts only
`PENDING → REACHED_OUT`; anything else returns 409/422, including re-marking an
already-reached-out lead (409, keeping the audit story clean). The dashboard displays
the state as "REACHED OUT" — the underscore form is API-only.

## 5. API contract

| Endpoint                        | Auth | Purpose                                              |
|---------------------------------|------|------------------------------------------------------|
| `POST /api/leads`               | none | Create lead. `multipart/form-data` (fields + file). Returns 201 + lead JSON (no resume path leaked). Idempotent per email: a duplicate (case-insensitive) returns 409 — enforced by a unique index, not just an app-level check, so concurrent submits can't race past it. |
| `GET /api/leads`                | 🔒   | List leads, newest first. Pagination via `limit`/`offset`. |
| `GET /api/leads/{id}`           | 🔒   | Single lead detail.                                  |
| `PATCH /api/leads/{id}`         | 🔒   | Body: `{"state": "REACHED_OUT"}`. Only valid transition allowed. |
| `DELETE /api/leads/{id}`        | 🔒   | Remove a lead and its stored resume (204). Storage cleanup is best-effort — the DB row is the source of truth. Added so e2e runs can clean up after themselves (§9); doubles as an admin tool. |
| `GET /api/leads/{id}/resume`    | 🔒   | Stream the resume file for attorney review.          |
| `POST /api/auth/login`          | none | Fallback credentials → JWT for the internal UI.      |
| `POST /api/auth/google`         | none | Google ID token → same JWT, after signature/audience verification and allowlist check. |

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

As built for this demo: the OAuth client is a **personal GCP project's client ID**
(type: Web application, `http://localhost:3000` as the authorized JavaScript origin).
Only the public client ID is needed — no client secret ships anywhere — and the
allowlist holds my own Gmail addresses, so real Google sign-in works out of the box
against my accounts. A production deployment swaps in a company GCP project and
allowlist via the same two env vars (`GOOGLE_CLIENT_ID`, `ADMIN_ALLOWED_EMAILS`).

Fallback flow: env-configured credentials (`ADMIN_EMAIL`/`ADMIN_PASSWORD`, defaulting
to `attorney@example.com`) exchanged for the same JWT — kept so reviewers can run the
E2E demo without creating a Google OAuth client. The default email is deliberately an
RFC-reserved `example.com` address so the repo never ships anything resembling a real
account. Disable in production by rotating the password.

One implementation subtlety both login paths share: after storing the token the app
does a **full navigation** to `/admin` (`window.location.assign`, not `router.push`).
Next.js prefetches `/admin` from the nav link before login and the client router
caches the middleware's redirect-to-login response, so a client-side push would
bounce straight back to the login page. Caught by the Playwright suite (§9) against
the production build — dev mode doesn't prefetch, so only e2e testing surfaced it.

*Production path (documented, not built):* per-attorney records with roles instead of
an env allowlist, HttpOnly session cookies via a BFF pattern, audit log of who marked
each lead.

## 7. Email flow

- Provider: **Resend** (simple API, generous free tier). Wrapped behind an
  `EmailService` interface with a **console/log fallback** so the app runs locally
  with zero API keys — the fallback prints the rendered email to stdout.
- Sender domain: `pactfulapp.com` — a personal domain I already owned from an
  unrelated side project, verified in Resend (DKIM/SPF) so delivery to *arbitrary*
  prospect addresses could be tested end-to-end. Resend's unverified sandbox sender only
  delivers to the account owner's inbox, which is fine for smoke tests but doesn't
  prove the real prospect-confirmation path. The domain is pure configuration
  (`EMAIL_FROM`); a production deployment would swap in the company domain.
- Two templates on lead creation:
  1. **Prospect confirmation** — "Thanks {first_name}, we received your information."
  2. **Attorney notification** — lead summary (name + email) and a plain-text pointer
     to the admin dashboard.
- **No hyperlinks in either template** — a deliverability lesson learned the hard way:
  Gmail silently dropped the attorney notification when it carried an
  `http://localhost:3000/admin` dashboard link (accepted by Resend with a 200, never
  delivered — confirmed by A/B testing identical emails with and without the link).
  Unit tests now pin both templates as link-free.
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

## 9. Testing

Three layers, cheapest first; each layer only covers what the one below it can't.

1. **Hermetic API tests** (`backend/tests`, plain `pytest`) — in-memory SQLite, a
   recording email fake, local-disk storage in a tmp dir. Cover validation, the
   state machine, auth, deletion, and that storage keys never leak into responses.
   Run in well under a second with no services.
2. **API e2e** (`backend/tests/e2e`, `pytest -m e2e`) — the same contract against the
   real docker stack: Postgres, a byte-for-byte resume roundtrip through MinIO, and
   the Next.js middleware gate. Excluded from the default `pytest` run via `addopts`;
   skips with a clear message when the stack isn't up.
3. **Browser e2e** (`frontend/e2e`, Playwright) — real user journeys against the
   running stack: prospect submits the form (including file upload and validation
   errors); attorney signs in with the fallback credentials, sees the lead, downloads
   the resume, marks it reached out; auth gating and sign-out. Playwright over
   Cypress/Selenium: out-of-process control means downloads and the Google Sign-In
   iframe just work, assertions auto-wait, and the trace viewer makes failures
   debuggable from artifacts alone.

`scripts/e2e.sh` runs layers 2 and 3 back to back.

**Test-data hygiene:** every e2e run deletes the leads it created — after first
asserting they actually appeared in the admin list — via `DELETE /api/leads/{id}`
(tracked automatically in the Playwright helpers, inline in the pytest lifecycle
test). The dashboard shows real data; test runs must not clutter it.

This layering earned its keep immediately: the Playwright suite caught the
production-build-only login bounce described in §6 that dev-mode testing and the
API-level tests structurally could not see.

## 10. Repo structure

```
.
├── README.md            # how to run locally (docker compose up) and run the tests
├── DESIGN.md            # this document
├── NOTES.md             # running agent-usage / attribution log
├── AI_USAGE.md          # final ½-page agent-usage writeup (from NOTES.md)
├── docker-compose.yml   # postgres + minio + backend + frontend
├── scripts/
│   └── e2e.sh           # runs both e2e suites against the docker stack
├── backend/
│   ├── app/
│   │   ├── main.py            # app factory, router mounting
│   │   ├── api/               # routers: leads.py, auth.py
│   │   ├── core/              # config (pydantic-settings), security
│   │   ├── models/            # SQLAlchemy models
│   │   ├── schemas/           # pydantic request/response schemas
│   │   ├── services/          # email.py, storage.py, leads.py (state machine)
│   │   └── db/                # session, Alembic migrations
│   ├── tests/                 # hermetic API tests (SQLite + fakes)
│   │   └── e2e/               # API contract vs. the live stack (pytest -m e2e)
│   └── pyproject.toml
└── frontend/
    ├── app/
    │   ├── page.tsx           # public lead form
    │   ├── admin/page.tsx     # leads dashboard (guarded)
    │   └── admin/login/page.tsx
    ├── middleware.ts          # cookie-presence gate for /admin routes
    ├── lib/api.ts             # typed API client
    ├── e2e/                   # Playwright browser journeys + cleanup helpers
    └── playwright.config.ts
```

## 11. Key decisions & tradeoffs

| Decision | Choice | Why / alternative rejected |
|---|---|---|
| AI lead scoring | **Not built** | Not in requirements; the assignment evaluates agent *usage*, not AI features. 6-hour budget goes to required deliverables. Noted as future work. |
| DB | Postgres (docker) | "Production-level" signal; SQLite alone reads as toy. SQLite kept for tests. |
| Email | Resend + console fallback | Reviewer can run E2E without secrets; real integration still demonstrated. |
| Emails async? | BackgroundTasks, post-commit | Submission UX must not depend on the email provider; full queue is overkill here. |
| Auth | Google OAuth + email allowlist, JWT in cookie, Next middleware gate | Real OAuth without secrets (ID-token flow); allowlist re-checked per request server-side. Env-credential fallback kept so reviewers can run the demo with zero OAuth setup. |
| Resume storage | MinIO (S3 API) via boto3 | Same code path as production S3 — promoting to AWS is config-only. Local-disk fallback keeps tests and no-docker dev dependency-free. MinIO complements Postgres (files vs. queryable lead rows); it does not replace it. |
| Monorepo | Yes | One clone, one compose file, one README — reviewer friction matters. |
| Browser e2e | Playwright | Out-of-process (downloads + Google iframe work), auto-waiting, trace viewer. Kept to the critical journeys — edge cases live in the cheaper pytest layers. Caught a real production-build-only login bug (§6). |
| Lead deletion | Admin-only `DELETE`, added late | Needed so e2e runs clean up after themselves; e2e suites verify a lead appears in the list before removing it. Resume removed from storage best-effort. |
| Test credentials | `attorney@example.com` fallback | RFC-reserved fake domain — the repo must never contain anything that reads as a real person's account or password. |

## 12. Out of scope / future work

- AI-assisted lead qualification (e.g., visa-fit summary from the CV)
- Multi-attorney routing / assignment, lead notes, richer state machine (e.g., `CLOSED`)
- Rate limiting / CAPTCHA on the public form (mention: it's a spam target)
- Delivery tracking for emails, S3 storage, real SSO
