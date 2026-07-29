import { isAxiosError } from "axios";

/** Mirrors the backend's `{"error": {code, message, details}}` envelope
 * (see `apps/backend/src/core/error_handlers.py` and `docs/ERROR_CODES.md`). */
export interface ApiError {
  code: string;
  message: string;
  details: Record<string, unknown> | null;
}

interface ErrorEnvelope {
  error?: {
    code?: string;
    message?: string;
    details?: Record<string, unknown> | null;
  };
}

/** Extracts the backend's typed error from a failed request, or `null` if
 * the response isn't in the expected envelope shape (network error, a
 * non-JSON response, etc.) — callers decide their own fallback message. */
export function parseApiError(error: unknown): ApiError | null {
  if (!isAxiosError(error) || !error.response) {
    return null;
  }
  const body = error.response.data as ErrorEnvelope | undefined;
  if (!body?.error?.code || !body.error.message) {
    return null;
  }
  return {
    code: body.error.code,
    message: body.error.message,
    details: body.error.details ?? null,
  };
}
