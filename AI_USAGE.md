# AI / Coding-Agent Usage

> ½-page writeup per the submission guidance. The raw chronological log lives in
> [NOTES.md](NOTES.md); commit trailers mark agent-generated code.

## Tools used

**Claude Code** (CLI, model: Claude Fable 5) as the primary coding agent, used
conversationally: requirements analysis and design discussion first, then delegated
implementation, with the agent running its own verification (pytest, `next build`)
before handing code back.

## What was delegated vs. decided by hand

**Delegated to the agent:** the E2E implementation — FastAPI app (routes, JWT auth,
Alembic migration), service layer, Next.js pages and API client, Dockerfiles/compose,
tests, and first drafts of README/DESIGN docs.

**Decided by hand (human):** product framing and scope (notably: *rejecting* AI lead
scoring as out of scope — see NOTES.md Disagreement #1), the email-provider choice
(Resend), the hard requirement that lead persistence be decoupled from email delivery,
Docker as the run story, and review/approval of every file before commit.

## One place the agent produced wrong or subtly bad code

The agent's console-fallback email transport "sent" emails via `logger.info(...)` —
but under uvicorn the app's loggers have no handler, and Python's last-resort handler
drops anything below WARNING. Result: submission emails were **silently discarded**
while every test stayed green (the unit tests assert against a recording fake, not the
logs) and every API call returned the correct status. It was caught only because the
docker-compose E2E smoke run included a step that grepped the backend logs for the
rendered emails and found zero. **Fix:** configure `logging.basicConfig(level=INFO)`
at app startup. The failure mode is instructive: the email path was deliberately
designed to be failure-tolerant, which also made its failure invisible — the demo path
itself had to be exercised end-to-end. (Smaller catches, detailed in NOTES.md: a
corrupted hex color token in generated CSS caught in diff review, and a too-short JWT
dev secret surfaced as a warning when the agent ran its own test suite.)

## Attribution

- Agent-generated commits carry a `Co-Authored-By: Claude` trailer.
- [NOTES.md](NOTES.md) is the per-session log of what was delegated, what was decided
  by the human, disagreements, and mistakes caught.

## Prompt logs / transcripts

Representative session excerpts are in [`transcripts/`](transcripts/). <!-- TODO:
export excerpts before submission: requirements walkthrough, the build session, and
the CSS-bug catch. -->
