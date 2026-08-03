# GroundTruth AI

An AI-verified talent marketplace. Every skill on a candidate's profile is backed by real
evidence — a verified GitHub contribution, a coding-platform record, a reachable certificate, or a
recorded answer in a code-grounded technical interview — and candidates and jobs are matched on
that same evidence, with the identical computed score shown to both sides.

> **Status: the full loop works end to end.** Candidate auth → profile → verification (real
> third-party API checks) → code-grounded AI interview → two-way matching → Smart Apply → recruiter
> Kanban pipeline → evidence card → messaging → analytics. **271 backend tests pass** (observed, not
> estimated). The whole stack runs containerized: `api` + three independently-scalable worker tiers
> + `web`, all health-checked.
>
> **Three honest gaps**, each requiring a credential or tool this environment doesn't have — see
> [PROGRESS.md §6](PROGRESS.md): no live LLM/embedding API key (so AI *output quality* is proven
> only against stubs plus one live graceful-degradation run), no browser click-through of the
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
- **Database** — PostgreSQL + pgvector, 7 Alembic migrations
- **Background work** — Celery + Redis, four queues (`extraction`, `verification`, `matching`,
  `dead_letter`) split by workload shape so slow LLM work can't head-of-line block a fast check
- **Object storage** — S3-compatible (MinIO locally, S3/R2 in production)
- **AI** — Anthropic (Claude) for extraction/interview/job-requirements behind one provider seam;
  OpenAI `text-embedding-3-small` for embeddings (the one deliberate exception — Anthropic has no
  embedding API)
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

**Code-grounded interview.** Only a `VERIFIED` repository can be interviewed on. Questions are
generated from that repository's *stored analysis* — not a generic question bank — and each answer
is scored against a fixed four-dimension rubric (`technical_accuracy 40% · depth_of_reasoning 25% ·
codebase_specificity 20% · repository_consistency 15%`) with a written rationale per dimension.
The resulting evidence report is never overwritten.

**Matching.** A two-step compute: a relational pre-filter (discoverability, graduation-year window,
location) bounds the candidate pool, then cosine similarity ranks within it. The rank-fusion score
is `100 × (0.5·semantic + 0.3·evidence + 0.2·profile_strength/100)`, threshold `50.0`. Below the
threshold, a pair simply isn't in `match_results` — it's absent from *both* sides, not hidden at
read time. Closing a job or losing discoverability prunes those rows, so the two feeds can't drift.

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

## 4. Repository layout

```
apps/backend/src/
  config/      one cached settings class per concern
  core/        exceptions, error envelope, authorization, pagination, request-id,
               logging, security headers, audit, crypto, mail/
  db/          engine/session/Base, register_models
  domains/
    auth/        13 endpoints, one shared users table, JWT + refresh cookie + CSRF
    student/     5-section profile builder, completeness scoring, evidence queueing,
                 GitHub OAuth connect + repo picker
    resume/      upload → parse → LLM extract → per-field review → confirm
    verification/ third-party clients (GitHub, Codeforces, LeetCode, HackerRank,
                 certificates) + scoring + skill derivation
    interview/   code-grounded interview state machine + rubric scoring
    recruiter/   job postings + the publish state machine
    matching/    embeddings, rank fusion, the two read paths
    pipeline/    Smart Apply, Kanban, evidence card, messaging, notes,
                 notifications, analytics
    ai/          the single LLM seam + provider adapters + prompt schemas
    skills/ company/ storage/
  jobs/        celery_app, dispatch, tasks/, polling + retry router
  platform/    async_jobs, audit_log
apps/frontend/src/
  features/    landing, auth, student, recruiter, messaging, notifications, jobs
  components/  shared primitives
  lib/         apiClient (auth + CSRF interceptor), queryKeys, apiError
docs/          DATA_MODEL.md, ERROR_CODES.md, API_REFERENCE.md
infra/docker/  docker-compose.yml (deps) + docker-compose.prod.yml (app tiers)
```

## 5. Testing

```bash
make test     # brings up the isolated test database, then runs pytest
```

**271 backend tests, all passing.** They run against `postgres-test` — a disposable,
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
email delivery asserted against captured messages *including submitting the OTP from the email
body back to the real endpoint*; and request-id propagation into worker logs.

**Not covered:** the LLM/embedding adapters themselves are stubbed (no API key in this
environment), there are no frontend tests (vitest is installed and wired with zero test files),
and there is no CI. See [PROGRESS.md](PROGRESS.md) for the full honest accounting.

## 6. Environment variables

`apps/backend/.env` — see `.env.example`, which is **verified complete**: every field across all
11 settings classes in `src/config/config.py` appears in it, with no orphaned entries.

| Group | Variables | Notes |
|---|---|---|
| App | `APP_ENV`, `APP_NAME`, `DEBUG`, `SECRET_KEY`, `FRONTEND_BASE_URL`, `ALLOWED_ORIGINS` | |
| Database | `DATABASE_URL` | Local dev points at the compose Postgres. Set via your platform's secret store in production. |
| Test database | `TEST_DATABASE_URL` | **Required to run tests.** Must resolve to a local host or `conftest.py` refuses to run. |
| Auth | `JWT_SECRET_KEY`, `JWT_ALGORITHM`, `JWT_ACCESS_TOKEN_EXPIRE_MINUTES`, `JWT_REFRESH_TOKEN_EXPIRE_DAYS`, `COOKIE_SECURE`, `TOKEN_ENCRYPTION_KEY` | Set `COOKIE_SECURE=true` in production. |
| Captcha | `RECAPTCHA_SITE_KEY`, `RECAPTCHA_SECRET_KEY` | Blank + `APP_ENV=development` bypasses verification. |
| Mail | `MAIL_BACKEND` (`console`\|`smtp`\|`capture`), `SMTP_HOST/PORT/USER/PASSWORD/USE_TLS/FROM_EMAIL` | `smtp` against MailHog (`localhost:1025`) locally. |
| OAuth | `GOOGLE_CLIENT_ID/SECRET/REDIRECT_URI`, `GITHUB_CLIENT_ID/SECRET/REDIRECT_URI/SCOPES` | Google = sign-in; GitHub = connecting a candidate's repos. |
| Celery | `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`, `JOB_MAX_RETRIES`, `JOB_RETRY_BACKOFF_*`, `JOB_*_TIME_LIMIT_SECONDS` | |
| Storage | `S3_ENDPOINT_URL`, `S3_REGION`, `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY`, `S3_RESUME_BUCKET`, `S3_PRESIGN_EXPIRY_SECONDS`, `RESUME_MAX_BYTES` | Bucket stays private; reads go through presigned URLs. |
| LLM | `DEFAULT_LLM_PROVIDER`, `ANTHROPIC_API_KEY`, `LLM_MODEL`, `LLM_MAX_TOKENS`, `LLM_EFFORT`, `LLM_TIMEOUT_SECONDS`, `LLM_MAX_RETRIES` | Only `anthropic` has an adapter; anything else raises `LLMNotConfigured`. |
| Embeddings | `OPENAI_API_KEY`, `EMBEDDING_MODEL`, `EMBEDDING_TIMEOUT_SECONDS`, `EMBEDDING_MAX_RETRIES` | |
| Verification | `GITHUB_API_TOKEN` (optional, raises GitHub's rate limit), `VERIFICATION_HTTP_TIMEOUT_SECONDS`, `*_RATE_LIMIT_PER_MINUTE` | |

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
credentials were available. See [PROGRESS.md §6](PROGRESS.md).

## 8. Documentation

| Document | Contents |
|---|---|
| [DEMO.md](DEMO.md) | 10-minute click path + seeded credentials |
| [PROGRESS.md](PROGRESS.md) | Honest per-module audit, real test counts, named gaps |
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
