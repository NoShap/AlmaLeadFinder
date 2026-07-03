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
the one-lead-per-email idempotency requirement (see below), Docker as the run story,
and review/approval of every file before commit.

## One place the agent produced wrong or subtly bad code

The agent's original public-form endpoint wasn't idempotent: every submission created
a new lead, so a prospect re-submitting the same email produced duplicate rows (and
duplicate resumes in storage) — something real users do constantly. Nothing failed:
every test was green, because the tests encoded the same assumption the code did.
This was a genuine disagreement — the agent had shipped it as acceptable behavior; I
pushed back and recommended one-lead-per-email idempotency. The agent then proposed
the design I accepted: emails normalized to lowercase, a friendly 409 *before* the
resume upload is accepted, and — because a pre-check alone can be raced by concurrent
submits — a **unique index** on `leads.email` as the actual source of truth
(`IntegrityError → 409`), plus a migration that lowercases and dedupes existing rows
(first submission wins, matching the new create semantics). The E2E suite gained an
explicit duplicate-409 step. The failure mode is instructive: the code was never
"broken," it was a missing product invariant that no amount of testing could surface,
because the tests shared the code's blind spot — it took a human looking at the
actual dashboard filling with duplicates. (Smaller catches, detailed in NOTES.md: the
console-fallback email transport logged below uvicorn's default level, silently
discarding demo emails until the docker E2E grepped the logs and found zero; a
corrupted hex color token in generated CSS caught in diff review; a too-short JWT dev
secret flagged when the agent ran its own test suite.)

## Attribution

- **All code in this repository was written by the coding agent.** The human
  contribution was direction, not authorship: scoping and framing each task,
  iteratively re-prompting and course-correcting where output missed the mark
  (see the idempotency case above), and reviewing every file before it was
  committed. Nothing shipped unread.
- Agent-generated commits carry a `Co-Authored-By: Claude` trailer.
- [NOTES.md](NOTES.md) is the per-session log of what was delegated, what was decided
  by the human, disagreements, and mistakes caught.

## Prompt logs / transcripts

Representative session excerpts are in [`transcripts/`](transcripts/). <!-- TODO:
export excerpts before submission: requirements walkthrough, the build session, and
the CSS-bug catch. -->
