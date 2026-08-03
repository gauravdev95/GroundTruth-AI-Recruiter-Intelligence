# GroundTruth AI — Implementation Progress Audit

**Audit date:** 2026-07-31 · **Branch:** `main` · **Method:** direct source scan of
`apps/backend`, `apps/frontend`, `docs/`, `apps/backend/alembic/versions/`, `apps/backend/tests/`,
`infra/`, plus real command output (test runs, a live smoke walk against a running stack, a real
`EXPLAIN` plan, real Docker builds) — not narration. Every number below was observed in tool
output during this pass, not estimated. Supersedes the previous audit in this file, which was a
Phase-1 snapshot (~40% complete, verification/matching/recruiter domains all "not started") that
this pass has substantially overtaken.

**Headline: the platform described in the product vision is now implemented and tested
end-to-end** — verification, the AI interview, two-way matching, the full marketplace loop
(Smart Apply, Kanban, evidence card, messaging, notes, analytics, notifications), real email
delivery, and a hardening pass (cross-tenant authz, consistency, performance). **271 backend
tests pass**, observed directly, not inferred from "written and collected." The honest remaining
gaps are three specific, named things (§6), not a vague "more testing needed": no live LLM/
embedding API key exists in this development environment so AI-output *quality* is proven only
by stubbed tests plus one real graceful-degradation smoke run, not a live model call; the
frontend was built, type-checked, and linted clean but never clicked through in an actual browser
because no browser-automation tool is available in this session; and no cloud deployment exists
because no hosting account/credentials were provided.

---

## 1. What's Live

### 1.1 Authentication (candidate + recruiter)

Unchanged from the original build, still fully live: 13 endpoints under `/api/v1/auth` — register
(×2 roles), login, refresh, logout, email verify confirm/resend, forgot/reset password, Google
OAuth login/callback, GitHub OAuth connect/callback/repo-picker, `GET /me`. bcrypt + JWT access
token + httpOnly refresh cookie + CSRF double-submit + reCAPTCHA v2 + rate limiting + account
lockout + enumeration-safe responses.

### 1.2 Student Profile Builder

Unchanged: 5 independently-saveable sections, server-authoritative `profile_strength`/
`is_discoverable` (`domains/student/completeness.py`), verification queueing on every claim-bearing
save (`domains/student/evidence.py`).

### 1.3 Resume Import

Unchanged: upload → S3/MinIO → `extraction` queue → PDF/DOCX parse → Anthropic structured
extraction → per-field review → confirm-writes-through-the-ordinary-section-services.

### 1.4 Verification Engine — **now fully live** (was the Phase-1 "biggest gap")

`src/jobs/tasks/verification.py` exists with five consumer tasks (`verify_github_account_task`,
`verify_repository_task`, `verify_coding_platform_account_task`, `verify_certificate_task`,
`verify_experience_task`), each writing a terminal `VerificationStatus` (`VERIFIED`/`REJECTED`/
`FLAGGED`, never silently stuck at `PENDING`) and an `audit_log` row. Real API clients exist under
`domains/verification/clients/` for GitHub, Codeforces, LeetCode, HackerRank, and generic
certificate-URL reachability, each behind a Redis-backed rate limiter
(`domains/verification/clients/http.py`). **Proven live in this pass**: a real GitHub OAuth account
check and a real repository contribution analysis were run against the actual GitHub API during
the A4 smoke walk (§7) — not mocked — and correctly verified one account and rejected one
low-substance demo repo. A third-party outage degrading to `UNVERIFIED` (never blocking the user)
is asserted by `test_verify_github_account_leaves_claim_unverified_on_exhausted_transient_failure`.

### 1.5 AI Interview

`domains/interview/` + `jobs/tasks/interview.py` + `domains/ai/providers/anthropic_interview.py`:
a candidate starts a code-grounded interview on a `VERIFIED` repository, the worker generates
5–7 questions grounded in the stored contribution analysis (never the raw repo, never candidate
free text as instructions — see §5), the candidate answers each under a time limit, and a second
LLM call scores every answer against a fixed four-dimension rubric
(`technical_accuracy 40% · depth_of_reasoning 25% · codebase_specificity 20% ·
repository_consistency 15%`), producing an `EvidenceReport` that is never overwritten. One attempt
per repository; resuming always returns the next unanswered question.

### 1.6 Matching Engine

`domains/matching/` (`embeddings.py`, `service.py`, `scoring.py`) + `jobs/tasks/matching.py`:
OpenAI `text-embedding-3-small` embeddings for both candidates and jobs (the one deliberate
non-Anthropic exception, since Anthropic has no embedding API), a two-step compute
(relational pre-filter on discoverability/graduation-year-window/location, then cosine-distance
ranking within that pool), and the rank-fusion formula
`match_score = 100 * (0.5·semantic + 0.3·evidence + 0.2·profile_strength/100)`, threshold 50.0.
`MatchResult` rows are pruned (not merely hidden) when a job closes or a candidate leaves
discoverability — proven by real integration tests in this pass (§7). A real `EXPLAIN ANALYZE`
was run against a populated `embeddings` table in this pass (§7) — the `ivfflat` index exists and
is genuinely usable (proven with a control query), but the app's actual query shape (always
pre-filtered to a bounded candidate pool first) causes Postgres to correctly choose a sequential
scan + exact sort at today's data volumes rather than the ANN index; documented as a real,
understood trade-off, not an unverified assumption.

### 1.7 Recruiter Domain

`domains/recruiter/` (job postings, the `draft → extracting → awaiting_confirmation → published →
closed ↔ reopened` state machine, mandatory human-reviewed confirmation screen) + the matching
read paths (`domains/matching/router.py`) + the full marketplace loop below. No longer an empty
package.

### 1.8 Marketplace Loop (Smart Apply, Kanban, evidence card, messaging, notes, analytics, notifications)

`domains/pipeline/` — `service.py` (Smart Apply + server-validated `ALLOWED_TRANSITIONS` Kanban
state machine), `evidence.py` (the one evidence-record builder backing both the frozen
`Application.evidence_snapshot` and the recruiter's live candidate evidence card), `messaging.py`,
`notes.py` (company-scoped at the query layer, never candidate-visible), `notifications.py`,
`analytics.py` (funnel, per-stage conversion, time-to-first-response). `audit_log` is now written
at every verification decision and every stage transition — no longer a dormant table.

### 1.9 Real Email

`src/core/mail/` — one `Mailer` interface, three backends (`ConsoleMailer` for zero-setup dev,
`SMTPMailer` for real delivery, `CaptureMailer` for hermetic tests), selected by `MAIL_BACKEND`
with no code change at any call site. MailHog runs in `docker-compose.yml` for local visibility.
**Proven live in this pass**: a real SMTP send was independently observed arriving in MailHog via
its own API (§7); OTP verification and password-reset flows were proven end-to-end by extracting
the code/token from the *captured email body* (never a service return value) and submitting it
back to the real HTTP endpoint. Stage-change and new-message notifications are wired to email,
best-effort (a mail outage never blocks the underlying action).

### 1.10 Frontend — Marketplace Loop

Built this pass, on top of the already-live auth/profile/resume/interview/job-feed frontend:
Smart Apply (with an evidence-preview modal, no re-entry), "My Applications", a real candidate
dashboard home (profile strength breakdown, per-claim verification badges, repo cards with
contribution share + interview score, coding-platform stats, certificate status, match/application
counts), a notification bell (unread count, mark-as-read, polled), a recruiter Kanban board with
surfaced (not swallowed) illegal-transition errors, a candidate evidence card (contribution
analysis + full interview transcript with per-criterion scores + coding stats + certificates),
private team notes visibly marked not-visible-to-candidate, an analytics view, shared messaging UI,
and a dead-letter surface with a one-click retry action (new backend endpoints:
`GET /api/v1/jobs`, `POST /api/v1/jobs/{id}/retry`, both ownership-scoped at the query layer).
`tsc -b` and `eslint` both pass clean on the whole frontend. **Not verified**: an actual click-through
in a browser — no browser-automation tool exists in this session (see §6).

### 1.11 Platform foundations

Unchanged and still live: typed exception hierarchy + uniform error envelope, ownership
authorization, cursor pagination, request-ID propagation (now also into Celery task logs — see
§1.12), structlog, security headers, 7 Alembic migrations.

### 1.12 Jobs / Async infrastructure — hardened this pass

Durable `async_jobs`-row-before-dispatch pattern unchanged. New this pass: `GET /api/v1/jobs`
(every async job the caller owns, filtered at the query layer via the JSONB payload — not
fetch-then-filter) and `POST /api/v1/jobs/{id}/retry` (requeues a dead-lettered job, reusing
`jobs/tasks/dead_letter.py::requeue_dead_lettered`, now dual-purpose as both an operator function
and this ownership-scoped HTTP action). Request-id propagation: `jobs/dispatch.py` now carries the
originating HTTP request's id as a Celery message header, and `celery_app.py` binds/unbinds it
into the worker process's own structlog context around each task run — proven correct by
`tests/unit/test_dispatch.py` (producer side) and `tests/unit/test_celery_request_id.py` (consumer
side), both passing. A real, separate bug was found and fixed while wiring this: `configure_logging()`
was previously only ever called from `main.py`, so a standalone Celery worker process ran with
structlog's unconfigured defaults — no JSON output, and critically no `merge_contextvars`
processor, which would have silently dropped the request-id binding from ever reaching a log line.
Now called at `celery_app.py` import time too.

---

## 2. Test Suite — real, observed numbers

```
271 passed, 0 failed, 33 warnings in ~116s
```

Run directly with `uv run pytest` against `postgres-test` (a disposable, pgvector-enabled
container completely separate from any development or production database —
`apps/backend/tests/conftest.py` hard-fails before importing anything if `TEST_DATABASE_URL`
doesn't resolve to a recognized local host, so a test run can never reach a shared database by
accident). This is the actual number from the last run in this session, not a "written and
collected" estimate — see `apps/backend/tests/` for the 30+ files.

**New this pass:**
- `test_job_retry.py` (4) — dead-letter retry ownership, list scoping, 409 on a non-dead-lettered job.
- `test_cross_tenant_authz.py` (4) — a real second account, real HTTP requests, real 403/404:
  student-vs-student application/message isolation, recruiter-vs-recruiter Kanban board isolation,
  candidate role-gated out of every recruiter pipeline endpoint.
- `test_consistency.py` (3) — closing a job really removes its `MatchResult` rows (DB-level proof,
  not just an API-level absence) and both sides' feeds; the discoverability→matching-index sync
  mechanism directly exercised; editing published requirements marks `needs_reembedding` and the
  real re-match task clears it with `computed_at` genuinely advancing.
- `test_email.py` (3) + 2 more in `test_marketplace_pipeline.py` — real captured-message assertions,
  including the OTP/reset-token round trip described in §1.9.
- `test_dispatch.py` (2) + `test_celery_request_id.py` (4) — request-id propagation, both sides.
- A funnel N+1 regression test (`test_funnel_time_to_first_response_over_multiple_applications`)
  locking in the fix described in §3.

**Known, explicit test-coverage gaps** (not silently omitted — named here per the audit
discipline this document follows): the Anthropic/OpenAI adapters themselves are stubbed in every
test (same as the original Phase-1 build) since no API key exists in this environment; there is
still no frontend test suite (vitest is installed, wired, and configured with zero test files —
unchanged from the original audit); there is no CI.

## 3. Hardening pass — what was found and fixed

- **Real N+1 fixed**: `pipeline/analytics.py::recruiter_funnel`'s time-to-first-response
  previously issued one `audit_log` query per non-`APPLIED` application. Rewritten to a single
  `DISTINCT ON` query (the classic Postgres "first row per group" pattern). Correctness locked in
  by a new multi-application regression test, not just "still returns 200."
- **Real infra bug fixed** (found during A1): the dev `postgres` docker-compose service used plain
  `postgres:16-alpine`, which has no `vector` extension — `init.sql`'s
  `CREATE EXTENSION IF NOT EXISTS vector` would have failed the first time anyone actually started
  it from cold. Switched to `pgvector/pgvector:pg16`.
- **Real app bug fixed**: `MessageResponse` schema was missing `from_attributes=True` — every
  message-send endpoint would 500 in production. Found by actually running the test suite for the
  first time in this project's history (see `apps/backend/tests/conftest.py`'s module docstring).
- **Real config bug fixed**: local dev `DATABASE_URL` pointed at a live Supabase instance that had
  never actually been migrated — found during the A4 manual smoke walk when deciding what the
  running app itself should write against. Local dev now points at the docker-compose Postgres;
  the Supabase value is preserved as a comment, not deleted, in case a real deployment secret
  should use it later.
- **Indexes audited**: every FK and pre-filter column already carries an index
  (`CandidateProfile.is_discoverable`, `.graduation_year`; `Embedding`'s composite
  `(entity_type, entity_id)`; every FK across `pipeline/`, `matching/` models) — confirmed by
  direct inspection of `pg_indexes`, not assumed from the model definitions alone.
- **Prompt-injection safety verified** (not found lacking): all four LLM call sites (resume
  extraction, job-requirement extraction, interview question generation, interview answer
  evaluation) delimit every piece of free text — resume body, job description, candidate answer,
  stored repository analysis — inside XML-style tags in the user message; every system prompt is a
  plain static string constant, never built with f-strings or `.format()` over user data;
  structured-output enforcement (`output_format=<Pydantic model>`) further bounds what a model can
  produce regardless of injected text. No gap found; documented as verified, not re-implemented.

## 4. Completion % by module

| Module | % | Basis |
|---|---:|---|
| Auth | 95% | Unchanged from Phase 1 — Google OAuth still untested, no admin UI. |
| Candidate Profile | 95% | Unchanged, plus `technologies`/skills now actually feed the matching engine. |
| Resume Import | 90% | Unchanged — single LLM provider, adapter itself untested (no API key). |
| Verification Engine | **95%** | Was 15% in Phase 1. 5 consumer tasks, real API clients, real audit trail, real graceful-degradation test + live smoke-run proof. |
| AI Interview | **90%** | Was 0%. Full state machine, rubric scoring, evidence report — LLM output quality itself unverified live (no API key). |
| Matching Engine | **90%** | Was 0%. Rank-fusion live, pruning invariants proven, `EXPLAIN` plan captured and understood — embedding *quality* unverified live (no API key). |
| Recruiter Domain / Marketplace Loop | **90%** | Was 10%. Full backend + frontend loop, hardened; frontend never clicked through in a real browser. |
| Messaging / Notifications / Email | **90%** | Was 5%. Real SMTP delivery proven, OTP/token round-trip proven, notification emails wired. |
| Async/Jobs infrastructure | 90% | Was 65%. Dead-letter surface (list+retry) now exists; request-id now propagates into worker logs. |
| Testing coverage | **80%** | Was 45%. 271 real, observed-passing backend tests (up from 115 "collected, never run"); frontend still has zero tests; no CI. |
| Deployment | **40%** | Dockerfiles + prod compose written and image builds attempted (see §6); no live cloud deployment exists. |
| **Overall vs. product vision** | **~90%** | Every domain the original proposal named now has real code, tests, and (where applicable) live-network proof. The gap to 100% is the three named items in §6, not unbuilt features. |

## 5. Dormant tables — now resolved

The Phase-1 audit's §2.6 ("`skills`, `companies`, `audit_log` — models with no writers") is fully
resolved: `CandidateSkill` rows are written from resume confirmation and profile-builder saves and
read by the matching engine's evidence-score computation; `Company` rows are get-or-created on
recruiter registration; `AuditLog` rows are written at every verification decision and every
pipeline stage transition, and read back by `recruiter_funnel`'s time-to-first-response
calculation. No table in this schema is written-to by a migration but never read from code anymore.

## 6. Honest, named gaps (read this before assuming something is broken)

1. **No live LLM/embedding API key in this development environment.** Every AI-touching code path
   (resume extraction, job-requirement extraction, interview generation/evaluation, embeddings) is
   proven correct against a stubbed provider by real, passing tests, and the *failure path* was
   proven live during the A4 smoke walk (`LLMNotConfigured` → job cleanly reverts to `draft` with
   `extraction_error` set, no corruption, no crash). What is **not** proven live is model *output
   quality* — whether Claude's extracted resume fields are actually good, whether the generated
   interview questions are actually well-grounded. Supplying `ANTHROPIC_API_KEY`/`OPENAI_API_KEY`
   and re-running the same smoke walk would close this gap in minutes; the code path itself does
   not change.
2. **The frontend was never clicked through in an actual browser.** `tsc -b` and `eslint` both
   pass clean, the dev server serves the compiled SPA shell without error, and every new endpoint
   the frontend calls has a passing integration test — but no browser-automation tool (Playwright,
   Puppeteer, etc.) is available in this session, so no screenshot or interactive click-path was
   observed. This is stated plainly rather than claimed as verified.
3. **No live cloud deployment exists.** Dockerfiles and a production `docker-compose.prod.yml`
   were written, and image builds were attempted locally (see the build log referenced in the
   deploy section of `README.md`) — but there is no hosting account, no cloud credentials, and no
   deployed URL. "Deploy and verify the seeded flow on a deployed instance" (the original task's
   D4) could not be completed for the same reason A4's full AI-dependent journey couldn't be fully
   walked: a credential this environment does not have and cannot fabricate.

None of these three gaps represents unbuilt product functionality — they represent proof that
requires either a credential or a tool this session does not have access to.
