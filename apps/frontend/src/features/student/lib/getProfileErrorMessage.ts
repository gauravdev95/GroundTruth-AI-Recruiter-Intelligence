import { isAxiosError } from "axios";

import { parseApiError } from "@/lib/apiError";

interface ValidationDetail {
  loc?: unknown[];
  msg?: string;
}

/**
 * Turns a failed section save into something a student can act on.
 *
 * The backend's 422 envelope carries FastAPI's raw error list in
 * `details.errors`. Its generic message ("The request failed validation")
 * says nothing useful, so the first field-level `msg` is surfaced instead —
 * that is the case where the client's zod mirror and the server's Pydantic
 * rules have drifted, and a vague banner would leave the student stuck.
 */
export function getProfileErrorMessage(
  error: unknown,
  fallback = "Could not save this section. Please try again.",
): string {
  if (!isAxiosError(error)) return fallback;

  if (error.request && !error.response) {
    return "Can't reach the server. Check your connection and try again.";
  }

  const apiError = parseApiError(error);
  if (!apiError) return fallback;

  if (apiError.code === "VALIDATION_FAILED") {
    const errors = apiError.details?.errors;
    if (Array.isArray(errors) && errors.length > 0) {
      const first = errors[0] as ValidationDetail;
      const field = Array.isArray(first.loc)
        ? first.loc.filter((part) => part !== "body").join(" → ")
        : "";
      if (first.msg) {
        return field ? `${field}: ${first.msg}` : first.msg;
      }
    }
  }

  return apiError.message;
}
