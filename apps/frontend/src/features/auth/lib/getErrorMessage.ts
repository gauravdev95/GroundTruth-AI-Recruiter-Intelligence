import { isAxiosError } from "axios";

/** Backend errors always come back as {"detail": string, "code": string}. */
export function getAuthErrorMessage(
  error: unknown,
  fallback = "Something went wrong. Please try again.",
): string {
  if (isAxiosError(error)) {
    if (error.response?.status === 429) {
      return "Too many attempts. Please wait a moment and try again.";
    }
    const detail = (error.response?.data as { detail?: string } | undefined)?.detail;
    if (typeof detail === "string" && detail.length > 0) {
      return detail;
    }
    if (error.request && !error.response) {
      return "Can't reach the server. Check your connection and try again.";
    }
  }
  return fallback;
}
