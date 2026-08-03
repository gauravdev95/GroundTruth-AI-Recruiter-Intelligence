import { Navigate, useLocation } from "react-router-dom";

/**
 * Rewrites `/candidate/<rest>` to `/student/<rest>`, preserving query and hash.
 *
 * The student lane lived at `/candidate` long enough to be bookmarked and to
 * appear in notification emails already delivered, so the old prefix redirects
 * rather than 404s. A bare `/candidate` lands on the dashboard.
 */
export function LegacyCandidateRedirect() {
  const location = useLocation();
  const rest = location.pathname.replace(/^\/candidate/, "") || "/dashboard";
  return <Navigate to={`/student${rest}${location.search}${location.hash}`} replace />;
}
