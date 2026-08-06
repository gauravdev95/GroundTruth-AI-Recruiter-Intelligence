# API Reference

Every endpoint mounted in `apps/backend/src/main.py`, grouped by domain. All paths are prefixed
`/api/v1`. Full request/response schemas live in each domain's `schemas.py`; this is a map, not a
substitute for reading them (or the live OpenAPI docs at `/docs` when the API is running).

Auth: **Bearer** = `Authorization: Bearer <access_token>` required. **Cookie** = relies on the
httpOnly refresh cookie + `X-CSRF-Token` header (set automatically by the frontend's axios
interceptor). **Public** = no auth. Every authenticated route also enforces role and ownership —
see each domain's `dependencies.py`.

## Auth (`/auth`)

| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/candidate/register` | Public | Candidate signup → access token + refresh cookie (signs in; no verification step) |
| POST | `/recruiter/register` | Public | Recruiter signup → access token + refresh cookie (signs in; no verification step) |
| POST | `/login` | Public | Email + password + captcha + `expected_role` → access token + refresh cookie |
| POST | `/refresh` | Cookie | Rotates the refresh token → new access token |
| POST | `/logout` | Cookie | Revokes the refresh token, clears cookies |
| POST | `/forgot-password` | Public | Always a generic success response (no enumeration) |
| POST | `/reset-password` | Public | `{token, new_password, confirm_password}`, single-use |
| GET | `/google/login?role=` | Public | Redirect to Google consent |
| GET | `/google/callback` | Public | Exchange code, create/link user, set cookies, redirect |
| GET | `/me` | Bearer | Current user |

**There is no email-verification step.** Both register endpoints return the same
`AccessTokenResponse` shape as `/login`, so a client goes straight from the signup form to the
dashboard with no second request. `/verify-email/confirm` and `/verify-email/resend` were
removed along with the `email_verification_tokens` table and the `users.is_email_verified`
column; nothing in the system establishes that a registrant controls their address, and the
password-reset flow proves ownership on its own where it matters.

## Student Profile (`/student/profile`)

| Method | Path | Purpose |
|---|---|---|
| GET | `/completeness` | Strength, discoverability, per-section state |
| GET / PUT | `/sections/basic` | Headline, college, degree, branch, grad year, location, target role, and `about` (optional — earns no completeness points, but feeds the profile embedding) |
| GET / PUT | `/sections/technical` | GitHub username + coding-platform handles |
| GET / PUT | `/sections/projects` | Up to 3 — a repo URL or a described project. **PUT does not accept `technologies`** — the request model forbids unknown keys, so sending it is a 422. A project's technologies are detected from its dependency manifests during verification and returned read-only on GET. |
| GET / PUT | `/sections/certificates` | Certificates and achievements |
| GET / PUT | `/sections/experience` | Internship / freelance / part-time history |

All Bearer, candidate-only, resolved via `get_own_profile` — no route takes a profile id.

## Student GitHub OAuth (`/student/github`)

| Method | Path | Purpose |
|---|---|---|
| GET | `/connect` | Returns a signed-state GitHub authorize URL |
| GET | `/callback` | GitHub redirect target — resolves candidate from signed state, writes `VERIFIED` |
| GET | `/repos` | Lists the connected account's repos for the picker |
| POST | `/repos/select` | Writes selected repos as `Project` rows, queues verification |

## Resume Import (`/student/resume`)

| Method | Path | Purpose |
|---|---|---|
| POST | `/uploads` | **202** — stores the file, queues extraction, returns a job id |
| GET | `/uploads` | List the caller's uploads |
| GET / DELETE | `/uploads/{id}` | Fetch / soft-delete an upload |
| GET | `/uploads/{id}/draft` | Latest extraction draft + per-section suggestions |
| GET | `/drafts/{id}` | A specific draft |
| POST | `/drafts/{id}/confirm` | Writes accepted sections through the ordinary section services |
| POST | `/drafts/{id}/discard` | Discards the draft |

## AI Interview (`/student/interview`)

| Method | Path | Purpose |
|---|---|---|
| POST | `/projects/{project_id}/start` | Starts an interview on a `VERIFIED` repository — **409** if not verified or one already exists |
| GET | `/projects/{project_id}/latest` | The latest attempt for a project |
| GET | `/{interview_id}` | Current state + next unanswered question (resumable) |
| POST | `/{interview_id}/questions/{question_id}/answer` | Submit an answer |
| GET | `/{interview_id}/report` | The evidence report — **409** until evaluation completes |

Interviews come in two groundings, distinguished by `interviews.grounding`:

- **`repository`** — started by the candidate via `/projects/{project_id}/start`, grounded in one
  `VERIFIED` repository's stored analysis. `project_id` is set.
- **`profile`** — created *by the system*, not by a request. There is no endpoint that starts one:
  `jobs/tasks/verification.py` creates it once verification settles and emails an invitation. It is
  grounded in the union of the candidate's verified evidence and has `project_id = NULL`. Once
  created it is fetched, answered, and reported through the same three endpoints above.

Both count toward the discoverability gate, and the report carries the `rubric_weights` of the
version that attempt was scored under — not the currently configured rubric.

## Recruiter Jobs (`/recruiter/jobs`)

| Method | Path | Purpose |
|---|---|---|
| GET | `` | List the caller's own job postings |
| POST | `` | Create a draft job |
| GET | `/{job_id}` | Job detail + extracted/confirmed requirements |
| PUT | `/{job_id}` | Update a draft (pre-publish only) |
| POST | `/{job_id}/submit` | **202** `draft → extracting` — queues AI requirement extraction |
| POST | `/{job_id}/requirements/edit` | `published → awaiting_confirmation` (requirements intact) |
| POST | `/{job_id}/confirm` | The mandatory human-reviewed confirmation → publishes, queues matching |
| POST | `/{job_id}/close` | `published → closed` — prunes every `MatchResult` for the job |
| POST | `/{job_id}/reopen` | `closed → published` — re-queues matching |

## Matching (`/recruiter/jobs/{job_id}/matches`, `/student/matches`)

| Method | Path | Purpose |
|---|---|---|
| GET | `/recruiter/jobs/{job_id}/matches` | Ranked candidates for one job |
| GET | `/student/matches` | The candidate's own ranked job feed |

Both are pure reads over `match_results` — nothing computed at request time.

## Marketplace Loop — Student (`/student`)

| Method | Path | Purpose |
|---|---|---|
| POST | `/jobs/{job_id}/apply` | Smart Apply — requires an existing `MatchResult`, snapshots evidence |
| GET | `/applications` | The caller's applications, with job title + company name |
| GET | `/applications/{id}` | One application's detail + frozen evidence snapshot |
| GET / POST | `/applications/{id}/messages` | Conversation with the recruiter on that application |
| GET | `/analytics/summary` | Match count, profile views, application outcomes |

## Marketplace Loop — Recruiter (`/recruiter`)

| Method | Path | Purpose |
|---|---|---|
| GET | `/jobs/{job_id}/pipeline` | The Kanban board — matched/applied/shortlisted/interview/hired/rejected |
| GET | `/applications/{id}` | Application detail + job/company/candidate context |
| POST | `/applications/{id}/transition` | Server-validated stage move — **409** on an illegal transition |
| GET | `/candidates/{candidate_profile_id}/evidence` | The full evidence card (requires a match or application relationship) |
| GET / POST | `/applications/{id}/messages` | Conversation with the candidate |
| GET / POST | `/applications/{id}/notes` | Private team notes — company-scoped, never candidate-visible |
| GET | `/analytics/funnel` | Stage counts, conversion, time-to-first-response |

## Notifications (`/notifications`)

| Method | Path | Purpose |
|---|---|---|
| GET | `` | The caller's notifications + unread count (either role) |
| POST | `/{id}/read` | Marks one notification read |

## Async Jobs (`/jobs`)

| Method | Path | Purpose |
|---|---|---|
| GET | `/{id}` | Poll one job's status — durable `async_jobs` row, not the Celery result backend |
| GET | `` | Every async job the caller owns — the dead-letter surface's data source |
| POST | `/{id}/retry` | Requeues a dead-lettered job (`FAILED` + `dead_lettered_at` set only) |

## Misc

| Method | Path | Purpose |
|---|---|---|
| GET | `/` | Liveness message |
| GET | `/health` | `{"status": "healthy", "database": "connected"}` — checks a real DB round trip |
| GET | `/docs` | Interactive OpenAPI (Swagger UI), non-production only |

## Error envelope

Every error response is `{"error": {"code": "...", "message": "...", "details": {...}}}`. See
`docs/ERROR_CODES.md` for the code catalogue and `apps/backend/src/core/error_handlers.py` for
the mapping.
