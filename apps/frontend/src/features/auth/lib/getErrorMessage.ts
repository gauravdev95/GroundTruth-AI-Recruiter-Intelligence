import { isAxiosError } from "axios";

import { parseApiError } from "@/lib/apiError";

/** Backend errors come back as {"error": {code, message, details}} — see `lib/apiError.ts`. */
export function getAuthErrorMessage(
  error: unknown,
  fallback = "Something went wrong. Please try again.",
): string {
  if (isAxiosError(error)) {
    if (error.response?.status === 429) {
      return "Too many attempts. Please wait a moment and try again.";
    }
    const apiError = parseApiError(error);
    if (apiError) {
      return apiError.message;
    }
    if (error.request && !error.response) {
      return "Can't reach the server. Check your connection and try again.";
    }
  }
  return fallback;
}
