import { Input } from "@/components";

import type { CodingPlatformType } from "../../api/profileApi";
import { CODING_PLATFORM_OPTIONS } from "../../constants";
import { FieldToggle } from "./FieldToggle";

export interface HandleState {
  included: boolean;
  value: string;
  fromResume: boolean;
}

export interface TechnicalFieldsState {
  github: HandleState;
  platforms: Record<CodingPlatformType, HandleState>;
}

interface TechnicalReviewProps {
  fields: TechnicalFieldsState;
  errors: { github?: string; platforms?: string };
  onGithubChange: (next: Partial<HandleState>) => void;
  onPlatformChange: (platform: CodingPlatformType, next: Partial<HandleState>) => void;
}

/**
 * Section 2 review.
 *
 * Confirming anything here queues a verification job for it — the same thing a
 * manual save does — so the copy says so rather than letting a student assume
 * an imported handle is already proven.
 */
export function TechnicalReview({
  fields,
  errors,
  onGithubChange,
  onPlatformChange,
}: TechnicalReviewProps) {
  return (
    <div className="space-y-3">
      <FieldToggle
        label="GitHub username"
        included={fields.github.included}
        fromResume={fields.github.fromResume}
        onToggle={(included) => onGithubChange({ included })}
        error={errors.github}
      >
        <Input
          placeholder="ada"
          value={fields.github.value}
          onChange={(event) => onGithubChange({ value: event.target.value })}
        />
      </FieldToggle>

      {/* Driven by the *state* the parent built, not by the full platform
          list. The two are not the same set and must not be assumed to be: the
          resume extractor only reads a handful of handles off a document, so
          iterating every platform the profile supports rendered a row for
          platforms that had no state at all. */}
      {(Object.keys(fields.platforms) as CodingPlatformType[]).map((platform) => {
        const state = fields.platforms[platform];
        const label =
          CODING_PLATFORM_OPTIONS.find((option) => option.value === platform)?.label ?? platform;
        return (
          <FieldToggle
            key={platform}
            label={`${label} handle`}
            included={state.included}
            fromResume={state.fromResume}
            onToggle={(included) => onPlatformChange(platform, { included })}
          >
            <Input
              placeholder="your_handle"
              value={state.value}
              onChange={(event) => onPlatformChange(platform, { value: event.target.value })}
            />
          </FieldToggle>
        );
      })}

      {errors.platforms ? (
        <p role="alert" className="text-xs text-[var(--failed)]">
          {errors.platforms}
        </p>
      ) : null}

      <p className="rounded-xl border border-[var(--rule)] bg-[var(--panel)] px-3 py-2 text-xs text-[var(--slate)]">
        Importing these queues them for verification — exactly as saving them by hand would. They
        stay <span className="font-medium text-[var(--flagged)]">pending</span> until GroundTruth has checked
        them.
      </p>
    </div>
  );
}
