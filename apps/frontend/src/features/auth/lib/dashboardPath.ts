import type { UserRole } from "../api/authApi";

/**
 * Where a freshly authenticated user belongs.
 *
 * Every sign-in path — the password form, the Google OAuth callback, and the
 * redirect out of a legacy `/login/{role}` URL — routes through this one
 * function. Previously each of them navigated to `"/"`, which dropped a user
 * who had just logged in back onto the marketing landing page and left them to
 * find their own dashboard.
 *
 * `admin` has no dashboard in this app; it lands on the landing page rather
 * than a route that would 403 immediately.
 */
export function dashboardPathForRole(role: UserRole): string {
  switch (role) {
    case "candidate":
      return "/student/dashboard";
    case "recruiter":
      return "/recruiter/dashboard";
    default:
      return "/";
  }
}
