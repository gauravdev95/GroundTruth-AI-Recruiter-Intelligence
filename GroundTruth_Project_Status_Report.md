# GroundTruth AI — Full Project Status Report

**Reviewed:** August 5, 2026 · Every non-vendor file and folder in the repo (excluding `apps/backend/.venv` and `apps/frontend/node_modules`, which are installed dependencies, not project code)

---

## 1. What the project is

GroundTruth AI is an AI-verified talent marketplace. Candidates prove skills through real evidence — verified GitHub contributions, coding-platform records, reachable certificates, and a code-grounded AI interview — and are matched against jobs using that same evidence, with identical scores shown to both candidate and recruiter.

It's a monorepo: a FastAPI/Python backend (`apps/backend`) and a React/TypeScript frontend (`apps/frontend`), plus Postgres, Redis, Celery workers, S3-compatible storage, and Anthropic/Gemini for AI work.

---

## 2. What is fully built

All twelve backend domains are implemented with real logic (not stubs), each following the same `router → service → models → schemas → dependencies → exceptions` structure:

**Auth** — signup, login, JWT + refresh cookie, Google OAuth, CSRF protection.

**Student profile** — 5-section builder (basic info, GitHub, coding profiles, projects, certificates/experience), completeness scoring, GitHub OAuth connect.

**Resume import** — upload → LLM extraction → per-field review → confirm. Full extraction pipeline (pattern matching, entry parsing, section detection, normalization, confidence scoring). Nothing the LLM extracts is saved unconfirmed.

**Verification** — real third-party API clients for GitHub, Codeforces, LeetCode, HackerRank, CodeChef, plus certificate reachability checks. Every claim resolves to `VERIFIED`, `REJECTED`, `FLAGGED`, or degrades to `UNVERIFIED` on outage — never left silently `PENDING`.

**AI interview** — two grounding modes (repository-based and profile-based), auto-generated once verification settles, scored against a 5-dimension weighted rubric with a written rationale per dimension, versioned so weight changes don't retroactively rescore past interviews.

**Matching engine** — SQL pre-filter (discoverability, graduation year, location, deadline) → pgvector cosine similarity → 5-term configurable rank fusion, threshold-gated (default 60.0). Runs on local `sentence-transformers` embeddings, so it needs no external API key.

**Recruiter jobs** — draft → AI-extracted requirements → recruiter confirms → publish.

**Pipeline/Kanban** — Smart Apply (immutable evidence snapshot), server-enforced Kanban state machine, evidence cards, private company-scoped notes, messaging gated on an existing pipeline relationship, funnel analytics, score-drift tracking.

**Realtime** — WebSocket push over Redis pub/sub for live pipeline updates.

**Async job infrastructure** — slow work returns 202 + a pollable `async_jobs` row, exponential backoff retries, dead-letter queue with one-click retry in the UI.

**Frontend** — a full marketing landing page, and complete student/recruiter dashboards mirroring every backend domain: onboarding wizard, resume review flow, interview UI, job feed, applications tracker, recruiter Kanban board with drag-and-drop, evidence drawer, notes panel, analytics pages for both sides.

**Infrastructure** — Docker Compose for both dev and prod topologies (API, 3 independently-scalable Celery worker tiers by queue, nginx-served frontend, Postgres+pgvector, Redis, MinIO, MailHog), a `Makefile` wrapping every dev command, and a backend `.env.example` that covers all 11 settings classes with no gaps.

**Testing** — 28 backend unit test files and 17 integration test files, covering auth, all profile sections, resume flow, every verification path including the outage-degrade case, interview scoring, matching, cross-tenant authorization, and consistency invariants. A handful of frontend component tests exist (7 files) but frontend test coverage is thin.

**Documentation** — this is unusually thorough for a project: `README.md` (387 lines, architecture + conventions), `DEMO.md` (scripted click-through with seeded test accounts), and `docs/API_REFERENCE.md`, `docs/DATA_MODEL.md`, `docs/ERROR_CODES.md`.

I checked the actual source code (not just the docs) for TODO/FIXME/stub/placeholder/`NotImplementedError` markers across both apps. Result: essentially clean. Backend has zero real hits. Frontend has exactly one: a commented-out placeholder for a future testimonials section on the marketing landing page (`apps/frontend/src/features/landing/BelowFold.tsx:46`) — cosmetic, not functional.

---

## 3. What is NOT complete or NOT verified

**No CI/CD.** There is no `.github/workflows` directory anywhere in the repo. Nothing runs automatically on push/PR.

**Two newest database migrations are unverified.** `e4c92a17f8d3` and `f1a83b6c25d9` (the last two of 16 total migration files — I counted the actual files, which is more than the "10" the README's stack-summary line states, though the detailed migration list elsewhere is consistent) have not had an Alembic upgrade/downgrade round-trip run against them, because Docker wasn't available in the session that wrote them.

**Integration test suite hasn't been run recently.** The 17 integration test files require a real Postgres+Docker environment; per the project's own README, this hasn't been executed against the current migration state.

**No live LLM/embedding calls verified.** No `ANTHROPIC_API_KEY`/`GOOGLE_API_KEY` was present in the environment that last touched this code, so the AI-dependent paths (resume extraction, interview generation, job-requirement extraction) have implementations but weren't exercised end-to-end with a real model call in that session. Embeddings are unaffected since they run locally.

**No browser click-through verification.** Frontend correctness was checked via `tsc -b` (typecheck) and `eslint` only — no one has actually driven the UI in a browser to confirm it behaves as coded.

**No cloud deployment.** Everything has been verified locally via Docker Compose only; there's no evidence this has ever been deployed to actual hosting.

**One cosmetic gap.** Testimonials section on the landing page is a known placeholder, not yet built.

**Minor doc inconsistency worth knowing about:** the README's stack summary (§2) says "10 Alembic migrations," but the actual `alembic/versions/` folder contains 16 migration files, and the detailed migration list in the README's own repository-layout section references the newer ones by name. This looks like a stale number in one summary line, not a real problem with the migrations themselves.

---

## 4. Bottom line

This is a substantially complete, working product — not a prototype with scaffolding. All 12 backend domains have real business logic, the frontend has matching UI for every one of them, the data model has a full migration history, and there's meaningful automated test coverage. The gaps that exist are exactly the operational-readiness ones you'd expect for a project that hasn't yet been pushed through a real deploy cycle: no CI pipeline, the newest two migrations and the full integration suite haven't been re-verified in the current environment, nobody's confirmed the AI calls work live with real API keys, nobody's clicked through the actual browser UI, and it's never been deployed anywhere but a local machine.

If you're deciding what to do next, the highest-value next steps in order would be: (1) run `make test` with Docker available to confirm the integration suite and newest migrations are sound, (2) put real `ANTHROPIC_API_KEY`/`GOOGLE_API_KEY` values in `.env` and manually exercise resume import, interview generation, and job extraction once, (3) do one full manual click-through per the `DEMO.md` script, (4) add a basic CI workflow (lint + unit tests) before anyone else touches the codebase.
