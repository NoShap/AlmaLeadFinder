# NOTES.md — Agent Usage Log

A running, chronological log of how coding agents were used on this project: what was
delegated, what was written/decided by hand, where the human and the agent disagreed,
and where the agent got things wrong. This is the raw material for `AI_USAGE.md`.

**Tooling:** Claude Code (CLI), model: Claude Fable 5.

**Attribution convention:** commits made through the agent carry a
`Co-Authored-By: Claude` trailer. Hand-written code is committed without it. Larger
mixed commits get a note here.

---

## 2026-07-02 — Session 1: Requirements analysis & system design

**Delegated to agent:** researched Alma's business (tryalma.com) to ground the domain
model; drafted `DESIGN.md` (architecture, data model, API contract, email flow, repo
structure).

**Human decisions:** overall direction; choosing to keep a running log (this file) from
the start rather than reconstructing agent usage at submission time.

**Disagreement #1 — AI lead scoring.** I (Noah) guessed the assignment wanted leads
*evaluated using AI*. The agent pushed back: the requirements never ask for it, and the
submission guidance says they're evaluating *how agents are used to build*, not AI
features in the product. Given the 6-hour window, we agreed to cut it and list it as
future work in DESIGN.md. Verdict: agent was right on scope; kept as an optional
stretch only if everything required is done.

**Agent choices I should verify, not rubber-stamp (open items):**
- [ ] Resend as email provider (vs SendGrid/Mailgun) — check free-tier signup friction
- [ ] Postgres-in-docker vs plain SQLite — is compose worth it for a reviewer's laptop?
- [ ] 409 vs idempotent 200 when re-marking a lead REACHED_OUT
- [ ] JWT roll-your-own vs NextAuth for the admin login

**Agent mistakes:** none caught yet. (Watch for: hallucinated library APIs, subtly
wrong SQLAlchemy 2.0 syntax, Next.js App Router client/server component mixups.)

---

## 2026-07-02 — Session 2: E2E implementation

**Human decisions (Noah):** confirmed Resend as the email provider; required that lead
persistence and email sending be decoupled; confirmed Docker as the local run story.

**Delegated to agent (all reviewed before commit):**
- Backend: FastAPI app (routers, JWT auth, config), SQLAlchemy `Lead` model + Alembic
  migration, service layer (state machine in `services/leads.py`, `EmailService`
  abstraction with Resend/console transports, `FileStorage` abstraction), 20 pytest
  API tests.
- Frontend: Next.js App Router pages (public form, admin login, admin dashboard),
  typed API client, styling.
- Infra: Dockerfiles, docker-compose (Postgres + backend + frontend), README.

**How the decoupling requirement landed:** `POST /api/leads` commits the lead, then
queues `send_lead_submission_emails` as a FastAPI background task. That function takes
plain values (not ORM objects) and swallows/logs provider failures. There's a dedicated
test (`test_email_failure_does_not_fail_submission`) proving a mail outage can't break
the form.

**Agent mistakes caught this session:**
1. *(cosmetic but real)* The agent's generated CSS contained a corrupted token —
   `--accent-hover: #17images3d2e;` — the string "images" spliced into a hex color.
   Caught on review right after the file was written; fixed to `#173d2e`. Classic
   example of plausible-looking generated output with a garbage token inside.
2. The agent's first pass used a JWT dev secret shorter than 32 bytes and a deprecated
   Starlette status constant — both surfaced as warnings when the agent ran the test
   suite, and were fixed before commit. (Counts as "caught by running the code, not by
   reading it.")

3. *(the subtle one — caught only by the E2E smoke test)* The `ConsoleEmailService`
   fallback "sends" emails via `logger.info(...)`, but under uvicorn the application's
   loggers have no handler configured, and Python's last-resort handler only emits
   WARNING and above — so the console emails were **silently dropped**. All 20 unit
   tests passed (they assert against a recording fake, not the logs), and every API
   call returned the right status; only a scripted docker-compose E2E run that grepped
   the backend logs for the rendered emails (found 0) exposed it. Fix:
   `logging.basicConfig(level=INFO)` in `create_app()`. Lesson: "decoupled and
   failure-tolerant" email dispatch also means email bugs are *invisible* by design —
   the demo path itself has to be tested.

**Verification:** backend `pytest` — 20/20 passing against SQLite + email fake.
Frontend `next build` — clean, all routes compile and type-check. Full docker-compose
E2E — scripted smoke test covering: health, public form submission, 401 without token,
login, authed list, resume download roundtrip (byte-identical), PENDING→REACHED_OUT,
409 on re-mark, console emails visible in logs, frontend pages serving. All passing
after fix #3.

---

## 2026-07-02 — Session 3: MinIO for resume storage

**Disagreement #2 — "MinIO instead of Postgres".** I (Noah) proposed swapping
Postgres+Docker for MinIO since we store resumes/large files and MinIO converts to S3
easily. The agent pushed back on the framing: MinIO is object storage and can't
replace the relational store (lead rows are queried, listed, and state-transitioned),
but it *should* replace the local-disk resume storage. Outcome: **Postgres stays for
lead data, MinIO added for resume files** — which still delivers the goal (S3-API
code path via boto3, so promoting to AWS S3 is config-only). Verdict: my instinct
about MinIO was right, my target was wrong; agent corrected the architecture.

**Delegated to agent:** `S3FileStorage` (boto3, bucket auto-create, per-process client
cache), generalizing `FileStorage` from disk-specific `full_path()` to
`save()/load()`, the download endpoint moving from `FileResponse` to bytes-from-
storage, MinIO compose service + config plumbing, doc updates.

**Design note:** selection is config-driven and mirrors the email service — S3 when
`S3_ENDPOINT_URL` is set, local disk otherwise — so tests and no-docker dev stay
dependency-free.

**Verification:** 20/20 tests passing (local-disk path); docker-compose E2E re-run
with resumes now stored in MinIO — roundtrip byte-identical; object confirmed in the
`resumes` bucket.

---

## 2026-07-02 — Session 4: Google OAuth + email allowlist

**Human decisions (Noah):** admin auth should be OAuth with an allowlist of three
specific Gmail addresses; wanted middleware guarding the admin pages and a check on
the lead status update.

**Agent's shaping of the request (accepted):**
- Tokens were in localStorage, which Next.js middleware cannot see — moved the JWT to
  a cookie so `middleware.ts` can gate `/admin/*`. Middleware is a UX gate only; real
  enforcement is server-side on every API endpoint.
- Chose Google Identity Services ID-token flow over NextAuth: needs only a public
  client ID (no secret, no session infra), and the backend verifies the token + maps
  it to the same app JWT the rest of the system already uses.
- Kept the env-credential login as a labeled fallback so a reviewer without a Google
  OAuth client can still run the demo E2E. (Terminology fix: the target state is
  REACHED_OUT per the assignment, not "Confirmed"; that PATCH was already
  auth-guarded and state-machine-checked — now it also re-checks the allowlist.)
- Allowlist is re-checked on **every request** in `require_admin`, not just at login,
  so delisting an email revokes access despite unexpired tokens. There's a test for
  exactly this (`test_valid_token_for_delisted_account_is_403`).

**Delegated to agent:** `/api/auth/google` endpoint (google-auth verification),
allowlist config + per-request enforcement, cookie token storage, `middleware.ts`,
GIS button on the login page, compose/env plumbing, 8 new auth tests.

**Agent mistakes caught this session:** `google-auth`'s requests transport needs the
`requests` package, which wasn't declared — the first test run failed with an
ImportError. Caught by running tests, fixed by adding the dependency.

**Verification:** 28/28 backend tests (incl. Google flow with faked verifier,
non-allowlisted 403, delisted-token 403); `next build` clean with middleware
registered; docker E2E extended with middleware redirect checks — see session log.

---
