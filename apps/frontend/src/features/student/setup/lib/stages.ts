import type { SectionKey } from "../../api/profileApi";
import type { SetupStepKey } from "../api/setupApi";

/**
 * The eight onboarding stages: their URL slugs, their order, and how far
 * through the flow each one is.
 *
 * ---
 *
 * **`percent` is progress through the flow, not profile strength, and the two
 * are deliberately different numbers.**
 *
 * `SetupState.completion_percentage` is the server's `profile_strength` — a
 * weighted score over what is *filled*, which this codebase computes
 * server-side and never derives on the client. It answers "how complete is
 * your profile". It is the right number for the profile-strength meter and the
 * wrong one for a wizard header, because a student who legitimately skips all
 * three optional stages finishes onboarding at 60% and is shown a bar that
 * says they failed.
 *
 * `percent` here answers a different question — "how far through this flow are
 * you" — and that is a fact the client genuinely knows, because position in a
 * fixed sequence is client state by definition. It is a constant per stage,
 * not a computation over anything, so it cannot drift from what the server
 * believes: there is nothing for it to disagree with.
 *
 * Both are shown, and they are labelled as what they are. See
 * `SetupProgressBar` for the header and `ProfileStrengthMeter` for the score.
 *
 * ---
 *
 * `sectionKey` is how a stage finds itself in `completeness.sections`; the two
 * bookends (`choose`, `review`) have none. `stepKey` matches the server's own
 * `SetupStep.key` so a stage can be paired with the server's status for it —
 * `setup_state.py::SETUP_STEPS` is the other half of this list and the order
 * here must match it.
 */
export interface OnboardingStage {
  /** Matches `SetupStep.key` from the server. */
  stepKey: SetupStepKey;
  /** The scored section behind this stage, or null for the two bookends. */
  sectionKey: SectionKey | null;
  /** Path segment under `/student/profile/setup`. Empty for the entry stage,
   * which is the index route. */
  slug: string;
  label: string;
  /** Position in the flow, 0-100. Not profile strength — see above. */
  percent: number;
  /** Mandatory stages have no "Skip for now". */
  isMandatory: boolean;
}

export const ONBOARDING_STAGES: readonly OnboardingStage[] = [
  { stepKey: "choose", sectionKey: null, slug: "", label: "Get started", percent: 0, isMandatory: true },
  { stepKey: "basic", sectionKey: "basic", slug: "basic-info", label: "Basic info", percent: 15, isMandatory: true },
  { stepKey: "github", sectionKey: "github", slug: "github", label: "GitHub", percent: 30, isMandatory: true },
  { stepKey: "projects", sectionKey: "projects", slug: "projects", label: "Projects", percent: 50, isMandatory: true },
  { stepKey: "coding", sectionKey: "coding", slug: "coding-profile", label: "Coding profile", percent: 65, isMandatory: false },
  { stepKey: "certificates", sectionKey: "certificates", slug: "certificates", label: "Certificates", percent: 80, isMandatory: false },
  { stepKey: "experience", sectionKey: "experience", slug: "experience", label: "Experience", percent: 90, isMandatory: false },
  { stepKey: "review", sectionKey: null, slug: "review", label: "Review & submit", percent: 100, isMandatory: true },
] as const;

/** The route prefix every stage hangs off.
 *
 * The spec writes these as `/onboarding/*`. They live under `/student/profile/setup`
 * instead because that subtree is already inside the `ProtectedRoute allow={["candidate"]}`
 * + `RedirectCompletedProfile` guards; a top-level `/onboarding` would sit
 * outside both and would need them rebuilt. The stage slugs themselves match
 * the spec exactly, so every stage is still its own back-button-safe,
 * resumable URL — which is what the route-per-stage structure was for.
 */
export const SETUP_BASE = "/student/profile/setup";

export function stagePath(stage: OnboardingStage): string {
  return stage.slug ? `${SETUP_BASE}/${stage.slug}` : SETUP_BASE;
}

export function stageBySlug(slug: string | undefined): OnboardingStage | undefined {
  return ONBOARDING_STAGES.find((stage) => stage.slug === (slug ?? ""));
}

export function stageByStepKey(key: SetupStepKey): OnboardingStage | undefined {
  return ONBOARDING_STAGES.find((stage) => stage.stepKey === key);
}

export function stageBySectionKey(key: SectionKey): OnboardingStage | undefined {
  return ONBOARDING_STAGES.find((stage) => stage.sectionKey === key);
}

/** The stage after `stage`, or `undefined` past the end. */
export function nextStage(stage: OnboardingStage): OnboardingStage | undefined {
  return ONBOARDING_STAGES[ONBOARDING_STAGES.indexOf(stage) + 1];
}

/** The stage before `stage`, or `undefined` at the start. */
export function previousStage(stage: OnboardingStage): OnboardingStage | undefined {
  const index = ONBOARDING_STAGES.indexOf(stage);
  return index > 0 ? ONBOARDING_STAGES[index - 1] : undefined;
}
