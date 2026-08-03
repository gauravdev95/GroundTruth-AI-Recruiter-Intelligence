# API Error Codes

Every error response uses the same envelope:

```json
{
  "error": {
    "code": "STABLE_MACHINE_READABLE_CODE",
    "message": "Human-readable message, safe to show a user",
    "details": { "request_id": "...", "...": "..." } // or null
  }
}
```

`details.request_id` is always present when the error occurred inside a request
(matches the `X-Request-ID` response header) — include it when reporting a bug so the
corresponding backend logs can be found. `code` is the stable identifier to branch on in
frontend code; `message` may change wording over time and should not be pattern-matched.

## Generic (`src/core/exceptions.py`)

| Code | HTTP status | Meaning |
|---|---|---|
| `NOT_FOUND` | 404 | The requested resource doesn't exist |
| `FORBIDDEN` | 403 | Authenticated, but not permitted (e.g. accessing another user's resource) |
| `CONFLICT` | 409 | Request conflicts with the resource's current state |
| `VALIDATION_FAILED` | 422 | Request body/query failed validation (Pydantic or a domain rule) |
| `EXTERNAL_SERVICE_ERROR` | 502 | An upstream/third-party service failed or is unavailable |
| `INTERNAL_ERROR` | 500 | Unexpected server error |

## Plain `HTTPException` (unrecognized status codes fall back to `HTTP_<status>`)

| Code | HTTP status | Raised by |
|---|---|---|
| `UNAUTHENTICATED` | 401 | `get_current_user` — missing/invalid/expired access token |
| `FORBIDDEN` | 403 | `require_role` — authenticated, wrong role |
| `NOT_FOUND` | 404 | Unmatched route |
| `METHOD_NOT_ALLOWED` | 405 | Wrong HTTP method for a matched route |
| `RATE_LIMITED` | 429 | (handled separately by `slowapi`'s own exception handler, not this envelope — see note below) |

## Authentication domain (`src/domains/auth/exceptions.py`)

| Code | HTTP status | Meaning |
|---|---|---|
| `EMAIL_ALREADY_REGISTERED` | 409 | Registration with an email already in use |
| `INVALID_CREDENTIALS` | 401 | Wrong email/password (also returned for a nonexistent email — enumeration-safe) |
| `ACCOUNT_LOCKED` | 423 | 5+ failed login attempts, temporarily locked |
| `ACCOUNT_INACTIVE` | 403 | Account deactivated |
| `ROLE_MISMATCH` | 403 | Login attempted against the wrong portal (candidate vs. recruiter) |
| `EMAIL_NOT_VERIFIED` | 403 | Login blocked pending email verification |
| `INVALID_OTP` | 400 | Wrong/expired/exhausted email verification code |
| `OTP_REQUEST_TOO_SOON` | 429 | OTP resend requested within the cooldown window |
| `INVALID_OR_EXPIRED_TOKEN` | 400 | Password-reset link invalid, expired, or already used |
| `CAPTCHA_FAILED` | 400 | reCAPTCHA verification failed |
| `INVALID_REFRESH_TOKEN` | 401 | Refresh cookie missing, invalid, expired, or revoked |
| `CSRF_FAILED` | 403 | Double-submit CSRF check failed on a cookie-authenticated endpoint |
| `OAUTH_NOT_CONFIGURED` | 503 | Google OAuth credentials not set in this environment |
| `OAUTH_ERROR` | 400 | Google OAuth exchange/consent failed |

## Student domain — GitHub OAuth (`src/domains/student/github_oauth.py`)

| Code | HTTP status | Meaning |
|---|---|---|
| `GITHUB_OAUTH_NOT_CONFIGURED` | 503 | GitHub OAuth credentials not set in this environment |
| `GITHUB_OAUTH_ERROR` | 400 | GitHub OAuth exchange/consent failed, or the state token was invalid/expired |

## Verification domain (`src/domains/verification/exceptions.py`)

These are internal to `src/jobs/tasks/verification.py` and are not raised
across an HTTP boundary — listed here because they drive the same
retryable/deterministic split as the LLM domain's errors, and because
`verification_payload.error` (surfaced read-only in the profile-section
responses) contains their message text when a check fails.

| Code | Meaning |
|---|---|
| `VERIFICATION_SERVICE_UNAVAILABLE` | Third-party API timed out, refused, or 5xx'd. Transient — retried, then leaves the claim `UNVERIFIED` |
| `VERIFICATION_RATE_LIMITED` | This worker's own rate limit for that third-party API was hit. Transient |
| `VERIFICATION_CLAIM_NOT_FOUND` | The claimed username/handle/URL does not exist. Deterministic — resolves the claim to `REJECTED`, not a job failure |

## Interview domain (`src/domains/interview/exceptions.py`)

| Code | HTTP status | Meaning |
|---|---|---|
| `REPOSITORY_NOT_VERIFIED` | 409 | Starting an interview on a project whose GitHub verification isn't `VERIFIED` yet |
| `INTERVIEW_ALREADY_EXISTS` | 409 | An interview for this `(candidate, project)` pair is already in progress or completed |
| `INTERVIEW_NOT_READY` | 409 | Question generation hasn't finished yet (`status=PENDING`) |
| `QUESTION_ALREADY_ANSWERED` | 409 | Resubmitting an answer to a question that already has one — answers are immutable |
| `INTERVIEW_NOT_COMPLETE` | 409 | Requesting the evidence report before evaluation has finished |

## Note on rate limiting

`slowapi`'s `RateLimitExceeded` is handled by its own bundled handler
(`slowapi._rate_limit_exceeded_handler`, registered in `main.py`) rather than this
envelope, since it's third-party middleware that runs before FastAPI's own exception
handling. It returns `429` with `slowapi`'s own response shape. Normalizing it into this
envelope is future cleanup, not required by this phase.
