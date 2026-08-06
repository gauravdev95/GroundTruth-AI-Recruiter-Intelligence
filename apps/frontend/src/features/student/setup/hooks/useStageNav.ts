import { useCallback, useMemo } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import {
  SETUP_BASE,
  nextStage,
  previousStage,
  stageBySlug,
  stagePath,
  type OnboardingStage,
} from "../lib/stages";

/**
 * Which stage the URL is on, and how to move between them.
 *
 * **The URL is the only source of truth for stage position.** The wizard this
 * replaced held the step index in component state seeded once from the
 * server's `current_step_index`, which meant the back button left the flow
 * entirely and a refresh mid-setup reopened at whichever step the server
 * thought was next rather than the one being looked at. One route per stage
 * makes both work for free, and makes a half-finished setup a link the student
 * can bookmark or reopen on another device.
 *
 * `advance` and `goBack` are separate from `skip` even though two of them do
 * the same navigation. They read differently at the call site — a form calls
 * `advance` only after a successful save, while `skip` is an explicit "I have
 * nothing here" — and keeping them distinct is what stops a future change to
 * one from silently changing the other.
 */
export function useStageNav() {
  const navigate = useNavigate();
  const { pathname } = useLocation();

  const stage = useMemo(() => {
    // The index route has no trailing segment; anything under the base does.
    const rest = pathname.startsWith(SETUP_BASE) ? pathname.slice(SETUP_BASE.length) : "";
    const slug = rest.replace(/^\/+/, "").split("/")[0] ?? "";
    return stageBySlug(slug);
  }, [pathname]);

  const goTo = useCallback(
    (target: OnboardingStage) => {
      navigate(stagePath(target));
      // The next stage mounts above the fold on a long form; without this the
      // student lands part-way down it.
      window.scrollTo({ top: 0, behavior: "smooth" });
    },
    [navigate],
  );

  const advance = useCallback(() => {
    if (!stage) return;
    const target = nextStage(stage);
    if (target) goTo(target);
  }, [goTo, stage]);

  const goBack = useCallback(() => {
    if (!stage) return;
    const target = previousStage(stage);
    if (target) goTo(target);
  }, [goTo, stage]);

  /** Optional stages only. Identical navigation to `advance`, deliberately a
   * different name — see the note above. */
  const skip = advance;

  return { stage, goTo, advance, goBack, skip };
}
