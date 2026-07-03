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
