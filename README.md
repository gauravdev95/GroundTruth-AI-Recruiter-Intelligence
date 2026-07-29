# GroundTruth AI

AI-powered engineering talent verification platform. Verifies candidate skills through GitHub repository analysis, contribution detection, static code analysis, AI repository understanding, an adaptive AI interview, and engineering evidence generation — surfaced to recruiters via semantic candidate search and to candidates via a student dashboard.

> **Status:** Phase 2 — authentication module. Building on the Phase 1 foundation, the backend now exposes a complete auth API (candidate + recruiter registration, email/password login, Google OAuth, email verification, password reset, refresh sessions) over a single shared `users` table, and the frontend has the full auth UI (role-select modal, login/signup/verify/reset pages) wired into the landing page. Dashboards and domain logic (Phase 3+) do not exist yet.

---

## 1. Technology Stack

- **Frontend:** React + Vite + TypeScript + Tailwind CSS
- **Backend:** FastAPI + SQLAlchemy 2.x + psycopg3
- **Database:** PostgreSQL (Supabase), with Alembic wired for future migrations

## 2. Folder Structure

```
apps/
├── frontend/
│   └── src/
│       ├── app/                App.tsx — BrowserRouter + QueryClient + AuthProvider, routes landing + auth
│       ├── features/
│       │   ├── landing/         public landing page (implemented — see below)
│       │   ├── auth/            authentication feature (implemented — see §8)
│       │   ├── student/         (empty so far)
│       │   └── recruiter/       (empty so far)
│       ├── components/         shared UI primitives (empty so far)
│       ├── hooks/               shared React hooks — useInView.ts (implemented)
│       ├── lib/                  apiClient.ts (axios + auth interceptor), tokenStore.ts, cookies.ts
│       ├── types/                shared TypeScript types (empty so far)
│       ├── styles/               index.css — Tailwind entry point
│       └── assets/               static assets (empty so far)
│
└── backend/
    └── src/
        ├── config/             config.py — DB + Security/Captcha/Email/GoogleOAuth settings from .env
        ├── db/                 database.py — engine/SessionLocal/Base/get_db/health-check (implemented)
        ├── core/               logging.py, middleware.py (security headers), error_handlers.py
        ├── domains/            auth/ (implemented — see §8), student/, recruiter/ (empty)
        ├── shared/             db_mixins.py — UUID PK + timestamp mixins
        └── main.py             FastAPI app: GET / and GET /health + mounted auth router

docs/architecture/                ADRs and diagrams go here as they're written
scripts/                           repo-wide dev/ops scripts (empty for now)
```

Only `auth`, `student`, and `recruiter` exist under `domains/` and `features/` — new domains/features get added only when work on them actually starts.

## 3. What's Already Implemented

- `apps/backend/src/config/config.py` — `DatabaseSettings`, loads `DATABASE_URL` from `.env`.
- `apps/backend/src/db/database.py` — SQLAlchemy `engine`, `SessionLocal`, `Base`, `get_db()` FastAPI dependency, and `check_database_connection()` health-check (`SELECT 1`). No tables, no `Base.metadata.create_all()`, no migrations.
- `apps/backend/src/main.py` — FastAPI app with `GET /` and `GET /health` (verifies the DB connection live and returns `{"status": "healthy", "database": "connected"}`).
- `apps/frontend/src/features/landing/` — the public marketing/landing page (`LandingPage.tsx`), split into `components/` (one file per section: `Nav`, `Hero`, `Problem`, `Pipeline`, `Interview`, `Evidence`, `Recruiter`, `Explainable`, `BuiltOn`, `Credibility`, `FinalCTA`, `Footer`, plus shared bits `Reveal`, `CountUp`, `SectionHead`, `Logo`), `data/` (static content arrays, typed via `types.ts`), and `styles/landing.css` (the page's own design system, independent of the Tailwind shell). `apps/frontend/src/hooks/useInView.ts` is the shared scroll-reveal hook it's built on.
- `apps/frontend/src/app/App.tsx` (+ `main.tsx`, `index.html`, `styles/index.css`) — root shell that renders `LandingPage`.

Everything else (routes, models, auth, dashboards) is intentionally not built yet.

## 4. Development Setup

Requirements: Node 20+ and Python 3.12+ with [`uv`](https://docs.astral.sh/uv/).

### Backend

```bash
cd apps/backend
uv venv
uv sync --extra dev
cp .env.example .env   # fill in DATABASE_URL and other values
uv run uvicorn src.main:app --reload
```

- http://localhost:8000/ → `{"message": "GroundTruth AI backend is running"}`
- http://localhost:8000/health → `{"status": "healthy", "database": "connected"}`

### Frontend

```bash
cd apps/frontend
npm install
cp .env.example .env
npm run dev
```

- http://localhost:5173/ → GroundTruth AI landing page.

### Convenience commands

```bash
make backend    # uv run uvicorn src.main:app --reload
make frontend   # npm run dev
make worker     # placeholder for when Celery is introduced
make migrate    # uv run alembic upgrade head
```

## 5. Environment Variables

Backend (`apps/backend/.env`, see `.env.example`):

| Variable | Purpose |
|---|---|
| `APP_ENV`, `APP_NAME`, `DEBUG`, `SECRET_KEY` | App identity/runtime flags |
| `DATABASE_URL` | PostgreSQL connection string (SQLAlchemy + psycopg3) |
| `POSTGRES_USER/PASSWORD/DB/HOST/PORT` | Individual DB connection parts (for tooling that wants discrete values) |
| `ALLOWED_ORIGINS` | CORS allow-list for the FastAPI app (used by `src/main.py`) |
| `REDIS_HOST`, `REDIS_PORT`, `REDIS_URL`, `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND` | Reserved for future background-job work |
| `SECRET_KEY`, `JWT_SECRET_KEY`, `JWT_ALGORITHM`, `JWT_ACCESS_TOKEN_EXPIRE_MINUTES`, `JWT_REFRESH_TOKEN_EXPIRE_DAYS` | Auth signing keys + token lifetimes (**used** by the auth module) |
| `COOKIE_SECURE`, `FRONTEND_BASE_URL` | Session-cookie `Secure` flag (set `true` in prod) + base URL for reset links / OAuth redirects |
| `RECAPTCHA_SITE_KEY`, `RECAPTCHA_SECRET_KEY` | Google reCAPTCHA v2. Leave blank in dev to bypass verification |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM_EMAIL` | Transactional email. Leave blank in dev to log OTP/reset emails to the console instead |
| `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_OAUTH_REDIRECT_URI` | Google OAuth 2.0 (Authorization Code flow). Button shows a "not configured" error until set |
| `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET`, `GITHUB_OAUTH_REDIRECT_URI` | Reserved for future GitHub OAuth |
| `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GROQ_API_KEY`, `DEFAULT_LLM_PROVIDER` | Reserved for future AI provider integration |

Frontend (`apps/frontend/.env`, see `.env.example`): `VITE_API_BASE_URL` (backend API base, **used** by `apiClient`), `VITE_RECAPTCHA_SITE_KEY` (reCAPTCHA v2 site key — blank in dev), plus reserved vars for future GitHub OAuth.

## 6. What's Deliberately Not Here Yet

No dashboards, no candidate/recruiter domain logic, no AI logic, no GitHub integration, no Docker/CI/Ruff/Mypy/Bandit/pre-commit. Phase 2 adds authentication only — a successful login lands back on `/` with the nav showing a logged-in state (no dashboard behind it yet).

## 7. Naming Conventions

- **Python:** `snake_case` for files/functions/variables, `PascalCase` for classes, domain folders are singular-concept nouns.
- **TypeScript/React:** `PascalCase` for components, `camelCase` for functions/variables/hooks, feature folders are singular lower-case nouns (`auth`, `student`, `recruiter`).
- **Env vars:** `UPPER_SNAKE_CASE`, prefixed `VITE_` on the frontend for anything exposed to the browser.

## 8. Authentication Module (Phase 2)

Two user types — **Candidate** (job seeker / student) and **Recruiter** (hiring manager) — authenticate against a **single shared `users` table**. Role-specific data lives in separate `candidate_profiles` / `recruiter_profiles` tables; there is no per-role auth table. `role` also includes `admin` for future use (no admin UI yet).

### Data model (`apps/backend/src/domains/auth/models.py`)

`users` (email, password_hash, role, full_name, verification/active flags, google_id, lockout counters) + `candidate_profiles`, `recruiter_profiles`, `refresh_tokens`, `email_verification_tokens`, `password_reset_tokens`. Passwords, refresh tokens, reset tokens, and OTPs are **only ever stored hashed**. Created by Alembic migration `alembic/versions/*_add_users_profiles_and_auth_tokens.py` — run `make migrate` (or `uv run alembic upgrade head`) to apply.

### Endpoints (`/api/v1/auth`)

| Method + path | Purpose |
|---|---|
| `POST /candidate/register` | Candidate signup → emails a 6-digit OTP |
| `POST /recruiter/register` | Recruiter signup → emails a 6-digit OTP |
| `POST /login` | email + password + captcha + remember_me + `expected_role`; sets refresh cookie, returns access token |
| `POST /refresh` | Rotates the refresh token (cookie-based, CSRF-checked) → new access token |
| `POST /logout` | Revokes the refresh token, clears cookies |
| `POST /verify-email/confirm` | `{email, otp}` |
| `POST /verify-email/resend` | Rate-limited OTP resend |
| `POST /forgot-password` | `{email}` → always a generic success response (no user enumeration) |
| `POST /reset-password` | `{token, new_password, confirm_password}` (single-use link token) |
| `GET /google/login?role=` | Redirect to Google consent |
| `GET /google/callback` | Exchange code, create/link user, set cookies, redirect to frontend |
| `GET /me` | Current user (requires access token) |

### Session model

Short-lived **JWT access token** returned in the response body and held in memory on the client (never in Web Storage — XSS can't read it). Long-lived **refresh token** in an `httpOnly`, `SameSite=Lax`, `Secure`-in-prod cookie, rotated on every `/refresh`. **Remember Me** switches the cookie between a persistent (N-day) and a browser-session cookie. Cookie-authenticated endpoints (`/refresh`, `/logout`) enforce a **double-submit CSRF token** (readable `csrf_token` cookie echoed back in the `X-CSRF-Token` header — done automatically by the axios interceptor).

### Security controls

bcrypt (cost 12) · JWT role-based auth + `require_role()` dependency · reCAPTCHA v2 (server-verified; dev-bypass only when `APP_ENV=development` and no secret set) · per-endpoint rate limiting (slowapi) · account lockout (5 failed logins → 15-min lock) · enumeration-safe login/forgot-password responses · CSRF double-submit · security headers (CSP, X-Frame-Options, etc.) via `core/middleware.py` · SQLAlchemy ORM only (no raw SQL) · Pydantic server-side validation mirrored by zod on the client.

### Frontend (`apps/frontend/src/features/auth/`)

Landing-page **"Login"** button (top-left of the nav) opens a glassmorphic **"Who are you?"** role-select modal → routes to the candidate or recruiter flow. Pages: candidate/recruiter login + signup, forgot/reset password, email verification (OTP input with countdown + resend), and the Google OAuth callback. State lives in `context/AuthContext.tsx` (silent refresh-on-load); API calls go through `hooks/useAuth.ts` → `api/authApi.ts` → the shared `lib/apiClient.ts` axios instance.

### Local email/OTP testing

With SMTP unset (the default in dev), verification and password-reset emails are **logged to the backend console** instead of sent — grep the uvicorn output for `email_dev_fallback` to read the OTP or reset link.

### Tests

`cd apps/backend && uv run pytest` — unit tests (password hashing, JWT round-trips, schema validation) + integration tests (full register→verify→login→refresh→logout, lockout, role mismatch, enumeration-safety, single-use reset). Integration tests run inside a rolled-back transaction against the configured database, so they leave no rows behind.

### External setup you must do yourself

reCAPTCHA keys (google.com/recaptcha/admin) and Google OAuth credentials (console.cloud.google.com) can't be generated here — drop them into `apps/backend/.env` (+ `VITE_RECAPTCHA_SITE_KEY` in `apps/frontend/.env`) when ready. Everything works locally without them (captcha bypassed, Google button reports "not configured").
