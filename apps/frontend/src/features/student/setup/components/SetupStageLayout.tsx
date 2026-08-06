import { Navigate, Outlet } from "react-router-dom";

import { useSetupState } from "../hooks/useSetupState";
import { useStageNav } from "../hooks/useStageNav";
import { SETUP_BASE } from "../lib/stages";
import { SetupProgressBar } from "./SetupProgressBar";

/**
 * The layout route wrapping stages 1-7. Renders the progress bar once, above
 * whichever stage the URL names.
 *
 * A layout route rather than a component each page renders, so the bar mounts
 * once and survives navigation between stages: a header that repaints on every
 * step reads as a page reload, and a page reload part-way through a form reads
 * as lost work.
 *
 * An unrecognised slug redirects to the entry stage rather than rendering an
 * empty frame. There is no such thing as a stage this flow does not know
 * about, so a URL naming one is a typo or a stale link, and the entry stage is
 * where both should land.
 */
export function SetupStageLayout() {
  const { stage, goTo } = useStageNav();
  const setupState = useSetupState();

  if (!stage) return <Navigate to={SETUP_BASE} replace />;

  return (
    <div className="space-y-6">
      <SetupProgressBar
        stage={stage}
        // Only the check marks come from here; the percentage is the stage's
        // own constant. `undefined` while in flight renders the rail unticked
        // rather than guessing which stages are done.
        steps={setupState.data?.steps}
        // Every stage stays reachable. Validation gates *advancing* — a form
        // only moves forward through its own successful save — never
        // *reaching*: refusing to open stage 6 because stage 5 is blank would
        // strand a student who has their internship dates to hand but not
        // their certificates, and this flow is explicitly multi-sitting. The
        // one hard gate is Submit, which the server rejects unless the
        // mandatory stages are complete.
        onSelect={goTo}
      />
      <Outlet />
    </div>
  );
}
