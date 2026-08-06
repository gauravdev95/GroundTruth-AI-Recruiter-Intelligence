# GroundTruth AI

An AI-verified talent marketplace. Every skill on a candidate's profile is backed by real
evidence — a verified GitHub contribution, a coding-platform record, a reachable certificate, or a
recorded answer in a code-grounded technical interview — and candidates and jobs are matched on
that same evidence, with the identical computed score shown to both sides.

> **Status: the full loop works end to end.** Candidate auth → profile → verification (real
> third-party API checks) → automatically-generated AI interview → two-way matching → Smart Apply →
> recruiter Kanban pipeline → evidence card → messaging → analytics. The whole stack runs
> containerized: `api` + three independently-scalable worker tiers + `web`, all health-checked.
>
> **Verification status of the current tree:** 259 backend *unit* tests pass, `tsc -b` and `eslint`
> are clean. The integration suite and an Alembic round-trip have **not** been run against the two
> newest migrations (`e4c92a17f8d3`, `f1a83b6c25d9`) — they need Docker, which was unavailable in
> the session that wrote them. Run `make test` before trusting the end-to-end claim above.
>
> **Three honest gaps**, each requiring a credential or tool this environment doesn't have:
> no live embedding API key (so matching cannot recompute — see §6), no browser click-through of the
> frontend (no browser-automation tool available; `tsc` + `eslint` pass clean), and no cloud
> deployment (no hosting credentials — the containerized stack was verified locally instead).

**Start here:** [DEMO.md](DEMO.md) — a 10-minute click path with seeded credentials that proves
verification, the code-grounded interview, and two-way matching.

---

## 1. Quick start

Requirements: Docker, and (for host-side development) Node 20+ and Python 3.12+ with
[`uv`](https://docs.astral.sh/uv/).

### Everything in containers

```bash
docker compose -f infra/docker/docker-compose.yml -f infra/docker/docker-compose.prod.yml up -d
make seed     # idempotent demo data — safe to re-run
```

| Service | URL |
|---|---|
| Web app | http://localhost:5173 |
| API + OpenAPI docs | http://localhost:8000 · http://localhost:8000/docs |
| MailHog (every outbound email) | http://localhost:8025 |
| MinIO console | http://localhost:9001 (`groundtruth` / `groundtruth-dev-secret`) |

### Host-side development

```bash
make infra                       # Postgres + Redis + MinIO + MailHog
cd apps/backend && uv sync --extra dev && cp .env.example .env
make migrate && make backend     # API on :8000
make worker                      # Celery, all four queues
cd apps/frontend && npm install && cp .env.example .env && npm run dev
```

### Commands

```bash
make infra / infra-down    # local dependency containers
make migrate               # alembic upgrade head
make backend / frontend    # dev servers
make worker                # celery worker, all queues
make test                  # starts the isolated test DB, then pytest
make test-db-up / -down    # the disposable test Postgres on :5433
make seed                  # idempotent demo data
```

## 2. Stack

- **Frontend** — React + Vite + TypeScript + Tailwind + TanStack Query + react-hook-form/zod
- **Backend** — FastAPI + SQLAlchemy 2.x (sync) + psycopg3 + Pydantic Settings
- **Database** — PostgreSQL + pgvector, 10 Alembic migrations
- **Background work** — Celery + Redis, four queues (`extraction`, `verification`, `matching`,
  `dead_letter`) split by workload shape so slow LLM work can't head-of-line block a fast check
- **Object storage** — S3-compatible (MinIO locally, S3/R2 in production)
- **AI** — **Google Gemini, and only Gemini.** Resume extraction, interview question generation,
  answer evaluation, and job-requirement extraction all go through one seam (`domains/ai/llm.py`)
  to one provider. No provider setting, no fallback: output that gets stored, ranked on, and shown
  to a recruiter as evidence should never be attributable to a model nobody selected.
  Embeddings are the one capability that is not a hosted API at all — `BAAI/bge-base-en-v1.5` runs
  in-process via `sentence-transformers`, so matching needs no key and makes no network call
- **Mail** — one `Mailer` interface, three backends (console / SMTP / in-memory capture) selected
  by `MAIL_BACKEND` with no code change

## 3. How it works

**Verification.** Saving a GitHub username, coding-platform handle, repo URL, or certificate sets
that claim to `PENDING` and enqueues a job in the same transaction. A worker calls the real
third-party API and writes a terminal status — `VERIFIED`, `REJECTED`, or `FLAGGED` — plus an
`audit_log` row. A third-party outage degrades to `UNVERIFIED` and never blocks the user; a claim
never silently sits at `PENDING`. Contribution share, detected technologies, and the raw evidence
the decision was based on are all stored, so "why does this candidate have this score" is always
answerable.

**Skills are never typed.** `candidate_skills` has exactly two write sites, both workers:
repository verification (technologies detected from dependency manifests) and coding-profile
verification (algorithmic competencies from a *verified* Codeforces/LeetCode record). The API does
not accept a `technologies` field on a project at all — sending one is a 422. The one place a
candidate still lists technologies is an **experience**, where the list is a claim submitted *for
corroboration*: it's checked against already-verified technologies, it never reaches
`candidate_skills`, and an experience can never exceed `FLAGGED`.

**AI interview, in two forms.** A **repository interview** is grounded in one `VERIFIED`
repository's stored analysis. A **profile interview** is grounded in the union of a candidate's
verified evidence — repositories, coding-profile stats, verified skills, corroborated certificates
and experience — and is generated *automatically* once verification settles, with an email
inviting the candidate to complete it. The profile interview is also the escape hatch that keeps
the discoverability gate honest: a candidate with no verifiable repository still has a route to a
completed interview, so nobody is permanently undiscoverable with no action available to them.

Answers are scored against a five-dimension rubric — `technical_accuracy 30% ·
code_understanding 25% · problem_solving 20% · repository_knowledge 15% · communication 10%` —
with a written rationale per dimension. Every weight is configurable (`INTERVIEW_WEIGHT_*`) and
validated to sum to 1.0 at process start. Changing them **does not** rescore past interviews: each
row records the `rubric_version` it was scored under, and an evidence report is written once and
never overwritten.

**Discoverability is earned in three stages.** Sections 1–2 complete → a profile vector exists →
a completed interview exists. Only then does a candidate enter the match computation. Each stage
gates the enqueueing of the next, so they must stay distinct — folding a later check into an
earlier flag deadlocks the chain and nobody is ever embedded, interviewed, or discoverable.

**Matching.** A two-step compute: a relational pre-filter (discoverability, graduation-year window,
location, deadline) bounds the candidate pool, then cosine similarity ranks within it. The
rank-fusion score is five configurable terms, `MATCH_WEIGHT_*`, defaulting to
`100 × (0.40·semantic + 0.25·skill_evidence + 0.15·interview + 0.10·competency +
0.10·profile_strength)`, threshold `MATCH_THRESHOLD` (default `60.0`). Weights must sum to 1.0 or
the process refuses to start. Below the threshold, a pair simply isn't in `match_results` — it's
absent from *both* sides, not hidden at read time. Closing a job or losing discoverability prunes
those rows, so the two feeds can't drift.

*Experience is deliberately absent from the score.* It has no independent source of truth and can
never reach `VERIFIED`, so weighting it would import unverified self-reports into a score whose
whole premise is verified evidence. It constrains eligibility in the hard filter instead.

**Three numbers, not one.** `profile_strength` is completeness (cannot fall when a claim is
rejected), `evidence_score` is the strength of verified evidence (can and should fall), and
`interview_score` is the best completed interview. One number could not express a complete profile
built on weak evidence *and* a sparse profile built on strong evidence.

**Marketplace loop.** Smart Apply snapshots the candidate's evidence at apply time (no data
re-entry). The recruiter's Kanban board enforces its state machine server-side —
`APPLIED → SHORTLISTED → INTERVIEW_SCHEDULED → HIRED`, with `REJECTED` reachable from any
non-terminal state — and an illegal transition returns 409 rather than being silently ignored.
Messaging is gated on an existing pipeline relationship; private team notes are company-scoped at
the query layer and have no candidate-reachable route at all.

**Async pattern.** Anything slow returns **202** with a job id, backed by a durable `async_jobs`
row (not the Celery result backend, which a broker flush would lose). Clients poll
`GET /api/v1/jobs/{id}`. Retries use exponential backoff; deterministic failures aren't retried;
exhausted jobs are dead-lettered and surface in the UI with a one-click retry.

## 3b. The candidate flow, end to end

```
Signup → Email verification → Login
   │
   ▼
Profile setup wizard ──► Resume upload (optional) ──► review & confirm per field
   │                        nothing the LLM extracted is saved unconfirmed
   ▼
Basic info (required) → GitHub + coding profiles (required) → GitHub projects (required)
   │                         certificates and experience stay optional
   ▼
┌─ background: verification queue ─────────────────────────────────────────┐
│  repository analysis → contribution + authorship → technology detection  │
│  coding-profile check (Codeforces/LeetCode only reach VERIFIED)          │
│  certificate reachability · experience corroboration                     │
│         ▼                              ▼                                 │
│  VERIFIED SKILLS                  VERIFIED COMPETENCIES                  │
│  (from manifests)                 (from coding profiles)                 │
└──────────────────────────────────────────────────────────────────────────┘
   │  verification settles (no claim left PENDING)
   ▼
Profile interview generated automatically  ──►  invitation email sent
   │
   ▼
Interview completed → interview_score → **discoverable = TRUE**
```

Recruiter side:

```
Job created → AI extracts requirements → recruiter confirms → job embedded
   │
   ▼
HARD FILTER (SQL)          discoverable · graduation-year window · location · deadline
   │  bounded pool only
   ▼
AI MATCHING (pgvector)     cosine similarity within the pool
   │
   ▼
RANK FUSION                5 configurable terms → match_score
   │
   ▼
score ≥ MATCH_THRESHOLD ?  ── no ──►  absent from match_results, both sides
   │ yes
   ▼
Recommended in the candidate's feed + the recruiter's Matched column
   │
   ▼
Smart Apply → immutable evidence snapshot → recruiter Kanban pipeline
```

## 4. Repository layout

A monorepo: two deployable apps plus shared infra and docs.

```
groundtruth/
├── apps/
│   ├── backend/            Python · FastAPI + Celery
│   └── frontend/           TypeScript · React + Vite
├── docs/                   reference docs (API, data model, error codes)
├── infra/docker/           compose files — deps + deployable app tiers
├── Makefile                every command you need (see §1)
├── README.md               you are here
└── DEMO.md                 10-minute click path with seeded logins
```

### Backend — `apps/backend/`

```
src/
├── main.py                 FastAPI app: middleware order, router mounts, /health
├── config/                 one cached settings class per concern (all env vars)
├── core/                   cross-cutting: errors, auth guards, logging, audit, mail/
├── db/                     engine, session, Base, register_models
├── shared/                 SQLAlchemy mixins (UUID pk, timestamps, soft delete)
├── platform/               async_jobs + audit_log tables
├── realtime/               WebSocket push over Redis pub/sub
├── jobs/                   Celery: queue topology, dispatch, tasks/, polling router
└── domains/                ← the business logic lives here, one folder per domain
```

Every domain follows the same shape, so learning one teaches you all of them:

| File | Role |
|---|---|
| `router.py` | HTTP endpoints. Kept thin — no business logic. |
| `service.py` | The actual logic. Where to start reading. |
| `models.py` | SQLAlchemy tables. |
| `schemas.py` | Pydantic request/response shapes. |
| `dependencies.py` | Auth, role, and ownership guards. |
| `exceptions.py` | Typed domain errors → stable API error codes. |

The twelve domains, in roughly the order a candidate hits them:

| Domain | What it owns |
|---|---|
| `auth/` | Signup, login, JWT + refresh cookie, Google OAuth, CSRF |
| `student/` | 5-section profile builder, completeness scoring, GitHub connect |
| `resume/` | Upload → parse → LLM extract → per-field review → confirm |
| `verification/` | Third-party checks (GitHub, Codeforces, LeetCode, certs) → **verified skills** |
| `interview/` | Repository + profile interviews, rubric scoring, evidence report |
| `matching/` | Embeddings, hard filter, rank fusion, both read paths |
| `recruiter/` | Job postings and the publish state machine |
| `pipeline/` | Smart Apply, Kanban, evidence card, messaging, notes, analytics |
| `ai/` | The single LLM seam + provider adapters + prompt schemas |
| `skills/` `company/` `storage/` | Small supporting tables and the S3 client |

```
alembic/versions/           schema history — append-only, never edit an applied one
scripts/                    seed.py (demo data) · recompute_profiles.py (backfill)
tests/unit/                 pure logic — no database, fast
tests/integration/          real Postgres, real HTTP, real transactions
```

### Frontend — `apps/frontend/src/`

```
├── app/                    App shell + routing
├── components/             shared primitives (Button, Input, Card, Toast…)
├── lib/                    apiClient (auth + CSRF interceptor), queryKeys, apiError
├── hooks/  types/  styles/
└── features/               ← one folder per product area
    ├── landing/            marketing page
    ├── auth/               signup, login, password reset
    ├── student/            setup wizard, profile sections, interview, matches
    ├── recruiter/          jobs, pipeline board, evidence card, analytics
    └── messaging/  notifications/  jobs/  realtime/
```

Each feature folder is self-contained — `api/` (server calls), `components/`,
`hooks/`, `pages/`, and its own `routes.tsx`. Nothing reaches into another
feature's internals; shared code moves up to `components/` or `lib/`.

## 5. Testing

```bash
make test     # brings up the isolated test database, then runs pytest
```

**259 backend unit tests pass.** The integration suite requires Docker and has not been run
against the two newest migrations — see the status note at the top. Integration tests run against
`postgres-test` — a disposable,
pgvector-enabled container on port 5433, entirely separate from any development or production
database. `apps/backend/tests/conftest.py` reads `TEST_DATABASE_URL` and **hard-fails before
importing anything** if it doesn't resolve to a recognized local host, so a test run can never
reach a shared database by accident. Each test runs inside a transaction that is rolled back at
teardown, even though the application code under test calls `commit()` internally.

Coverage includes: the full auth lifecycle; all five profile sections; the resume
upload→draft→confirm loop; every verification task including the degrade-to-`UNVERIFIED` outage
path; the interview state machine and rubric arithmetic; matching pre-filter and scoring; the
marketplace loop end to end; cross-tenant authorization (real second accounts, real 403/404);
consistency invariants (a closed job really leaves both feeds; re-embedding staleness clears);
email delivery asserted against captured messages *including submitting the password-reset token
from the email body back to the real endpoint*; and request-id propagation into worker logs.

**Not covered:** the LLM/embedding adapters themselves are stubbed (no API key in this
environment), there are no frontend tests beyond a handful of component tests, and there is no CI.

## 6. Environment variables

`apps/backend/.env` — see `.env.example`, which is **verified complete**: every field across all
11 settings classes in `src/config/config.py` appears in it, with no orphaned entries.

| Group | Variables | Notes |
|---|---|---|
| App | `APP_ENV`, `DEBUG`, `SECRET_KEY`, `FRONTEND_BASE_URL`, `ALLOWED_ORIGINS` | |
| Database | `DATABASE_URL` | Local dev points at the compose Postgres. Set via your platform's secret store in production. |
| Test database | `TEST_DATABASE_URL` | **Required to run tests.** Must resolve to a local host or `conftest.py` refuses to run. |
| Auth | `JWT_SECRET_KEY`, `JWT_ALGORITHM`, `JWT_ACCESS_TOKEN_EXPIRE_MINUTES`, `JWT_REFRESH_TOKEN_EXPIRE_DAYS`, `COOKIE_SECURE`, `TOKEN_ENCRYPTION_KEY` | Set `COOKIE_SECURE=true` in production. |
| Captcha | `RECAPTCHA_SITE_KEY`, `RECAPTCHA_SECRET_KEY` | Blank + `APP_ENV=development` bypasses verification. |
| Mail | `MAIL_BACKEND` (`console`\|`smtp`\|`capture`), `SMTP_HOST/PORT/USER/PASSWORD/USE_TLS/FROM_EMAIL` | `smtp` against MailHog (`localhost:1025`) locally. |
| OAuth | `GOOGLE_CLIENT_ID/SECRET/REDIRECT_URI`, `GITHUB_CLIENT_ID/SECRET/REDIRECT_URI/SCOPES` | Google = sign-in; GitHub = connecting a candidate's repos. |
| Celery | `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`, `JOB_MAX_RETRIES`, `JOB_RETRY_BACKOFF_*`, `JOB_*_TIME_LIMIT_SECONDS` | |
| Storage | `S3_ENDPOINT_URL`, `S3_REGION`, `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY`, `S3_RESUME_BUCKET`, `S3_PRESIGN_EXPIRY_SECONDS`, `RESUME_MAX_BYTES` | Bucket stays private; reads go through presigned URLs. |
| LLM | `GOOGLE_API_KEY`, `LLM_MODEL` (default `gemini-3.6-flash`), `LLM_MAX_TOKENS`, `LLM_TIMEOUT_SECONDS`, `LLM_MAX_RETRIES` | One provider, one key. Without `GOOGLE_API_KEY` the app still starts and resume upload still works via the deterministic parser, but interviews and job publishing fail with `LLM_NOT_CONFIGURED`. `LLM_MAX_RETRIES` is per *request*; the Celery job retries on top of it. |
| Embeddings | `EMBEDDING_MODEL`, `EMBEDDING_DEVICE`, `EMBEDDING_CACHE_DIR` | No key: runs in-process. `EMBEDDING_MODEL`'s output width must equal the pgvector column's — a different width needs a migration, and the process refuses to start rather than failing every insert. |
| Matching | `MATCH_THRESHOLD` (default `60.0`), `MATCH_WEIGHT_SEMANTIC`, `MATCH_WEIGHT_SKILL_EVIDENCE`, `MATCH_WEIGHT_INTERVIEW`, `MATCH_WEIGHT_COMPETENCY`, `MATCH_WEIGHT_PROFILE_STRENGTH` | **Weights must sum to 1.0 and be non-negative** — the process refuses to start otherwise, naming the offending vars. Threshold must be strictly between 0 and 100. |
| Interview | `INTERVIEW_RUBRIC_VERSION`, `INTERVIEW_WEIGHT_TECHNICAL_ACCURACY`, `INTERVIEW_WEIGHT_CODE_UNDERSTANDING`, `INTERVIEW_WEIGHT_PROBLEM_SOLVING`, `INTERVIEW_WEIGHT_REPOSITORY_KNOWLEDGE`, `INTERVIEW_WEIGHT_COMMUNICATION` | Same sum-to-1.0 enforcement. Changing weights does not rescore past interviews — each row stores its `rubric_version`. |
| Verification | `GITHUB_API_TOKEN` (optional, raises GitHub's rate limit), `VERIFICATION_HTTP_TIMEOUT_SECONDS`, `*_RATE_LIMIT_PER_MINUTE` (github, codeforces, leetcode, hackerrank, codechef, certificate_check) | |

`apps/frontend/.env`: `VITE_API_BASE_URL`, `VITE_RECAPTCHA_SITE_KEY`. Note these are **baked in at
build time** by Vite — the frontend Dockerfile takes them as build args, not runtime env.

## 7. Deployment

`infra/docker/docker-compose.prod.yml` defines the deployable topology:

| Service | Role |
|---|---|
| `migrate` | One-shot `alembic upgrade head`; everything else waits on it completing successfully |
| `api` | uvicorn, health-checked against `/health` (which does a real DB round trip) |
| `worker-extraction` | LLM-bound work — resume import, job-requirement extraction, interviews |
| `worker-verification` | Third-party checks, rate-limited per host, independently scalable |
| `worker-matching` | Embeddings + rank fusion, plus the dead-letter recorder |
| `web` | nginx serving the built SPA, with SPA-fallback routing |

Every service is health-checked; each worker tier scales independently:

```bash
docker compose -f infra/docker/docker-compose.yml -f infra/docker/docker-compose.prod.yml \
  up -d --scale worker-verification=3
```

The compose file loads `apps/backend/.env` for secrets and feature flags, then **overrides every
container-to-container address** (`DATABASE_URL`, `CELERY_BROKER_URL`, `SMTP_HOST`,
`S3_ENDPOINT_URL`) to compose service names — a container's own `localhost` is itself, never a
sibling. A real deployment swaps those to managed services.

**Verified locally:** both images build, all five application containers reach `healthy`, the
seeded flow was walked end to end through the containerized API (job feed, applications, evidence
snapshot with interview score, Kanban board, funnel analytics, evidence card, private notes,
cross-tenant 403, illegal-transition 409). **Not done:** a cloud deployment — no hosting
credentials were available.

## 8. Documentation

| Document | Contents |
|---|---|
| [DEMO.md](DEMO.md) | 10-minute click path + seeded credentials |
| [docs/API_REFERENCE.md](docs/API_REFERENCE.md) | Every endpoint, grouped by domain |
| [docs/DATA_MODEL.md](docs/DATA_MODEL.md) | ER design |
| [docs/ERROR_CODES.md](docs/ERROR_CODES.md) | Error envelope + code catalogue |

## 9. Conventions

- **Python** — `snake_case` files/functions, `PascalCase` classes, one domain package per bounded
  context, `router → service → models` with routers kept thin.
- **TypeScript/React** — `PascalCase` components, feature-folder layout, every API call goes
  through `lib/apiClient.ts`.
- **Env vars** — `UPPER_SNAKE_CASE`, `VITE_`-prefixed for anything reaching the browser.
- **Errors** — every failure returns `{"error": {code, message, details}}` with a request id.
