/**
 * Central query-key registry. One namespace per domain, each a factory
 * function (even for a fixed key) so a later parameterized variant
 * (`queryKeys.jobs.detail(id)`) doesn't change the calling convention.
 *
 * Only `auth.me` is wired to a real query today — `AuthContext` currently
 * calls `authApi.me()` directly during its silent-refresh-on-load effect,
 * not through `useQuery`. This entry documents the key a future
 * `useQuery({ queryKey: queryKeys.auth.me() })` migration would use, and
 * is the pattern new domains (`candidate`, `recruiter`, `jobs`, ...) append
 * their own namespace to.
 */
export const queryKeys = {
  auth: {
    me: () => ["auth", "me"] as const,
  },
} as const;
