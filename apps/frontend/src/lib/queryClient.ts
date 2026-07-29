import { QueryClient } from "@tanstack/react-query";
import { isAxiosError } from "axios";

/** Retries transient failures (network errors, 5xx) up to twice; never
 * retries 4xx — those won't succeed without the request itself changing. */
function shouldRetry(failureCount: number, error: unknown): boolean {
  if (failureCount >= 2) return false;
  if (isAxiosError(error) && error.response) {
    return error.response.status >= 500;
  }
  return true;
}

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 60_000,
      retry: shouldRetry,
      refetchOnWindowFocus: false,
    },
  },
});
