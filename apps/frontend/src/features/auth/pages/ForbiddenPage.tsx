import { useNavigate } from "react-router-dom";

import { Button, ErrorState } from "@/components";

/** Rendered by `ProtectedRoute` when an authenticated user's role isn't
 * allowed on the page they requested. */
export function ForbiddenPage() {
  const navigate = useNavigate();

  return (
    /*
     * The background is the app token, not the hardcoded light grey this page
     * used to carry — on the dark theme that grey was a white flash behind an
     * otherwise dark error state.
     */
    <div className="flex min-h-screen items-center justify-center bg-[var(--bg)] px-4">
      <div className="w-full max-w-md">
        <ErrorState
          title="You don't have access to this page"
          description="Your account doesn't have permission to view this. If you think that's wrong, contact support."
          action={
            <Button variant="secondary" onClick={() => navigate("/")}>
              Back to home
            </Button>
          }
        />
      </div>
    </div>
  );
}
