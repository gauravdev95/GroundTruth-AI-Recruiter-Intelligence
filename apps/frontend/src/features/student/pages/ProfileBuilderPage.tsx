import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { Button, ErrorState, Skeleton, useToast } from "@/components";

import type { SectionKey } from "../api/profileApi";
import { DiscoverabilityBanner } from "../components/DiscoverabilityBanner";
import { ProfileStepper } from "../components/ProfileStepper";
import { ProfileStrengthMeter } from "../components/ProfileStrengthMeter";
import { useProfileCompleteness } from "../hooks/useProfileSection";
// Shared with the setup flow's manual path, so both render the same form for a
// given section rather than two copies that can drift.
import { ActiveSection } from "../sections/ActiveSection";

export function ProfileBuilderPage() {
  const [activeSection, setActiveSection] = useState<SectionKey>("basic");
  const completeness = useProfileCompleteness();
  const [searchParams, setSearchParams] = useSearchParams();
  const { showToast } = useToast();

  // GitHub redirects the full browser page back to `?github=connected|error`
  // after the OAuth exchange (`domains/student/github_router.py::callback`)
  // — there is no JSON response to react to, only this query param.
  useEffect(() => {
    const github = searchParams.get("github");
    if (!github) return;

    if (github === "connected") {
      showToast("GitHub account connected.", "success");
      setActiveSection("technical");
    } else {
      showToast("Couldn't connect your GitHub account. Please try again.", "error");
    }

    const next = new URLSearchParams(searchParams);
    next.delete("github");
    setSearchParams(next, { replace: true });
    // Only ever fires off the URL param present on initial load/redirect —
    // re-running on every searchParams identity change would loop, since
    // `setSearchParams` itself changes it.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams]);

  if (completeness.isPending) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-96 w-full" />
      </div>
    );
  }

  if (completeness.isError) {
    return (
      <ErrorState
        title="Could not load your profile"
        description="We couldn't work out how complete your profile is. Please try again."
        action={
          <Button type="button" variant="secondary" size="sm" onClick={() => void completeness.refetch()}>
            Try again
          </Button>
        }
      />
    );
  }

  return (
    <div className="space-y-6">
      <header>
        <h1 className="font-display text-2xl font-semibold text-ink">Your profile</h1>
        <p className="mt-1 text-sm text-slate-500">
          Each section saves on its own — you can finish this over several sittings.
        </p>
      </header>

      <DiscoverabilityBanner completeness={completeness.data} />

      <div className="grid gap-6 lg:grid-cols-[minmax(0,17rem)_minmax(0,1fr)]">
        <aside className="space-y-4 lg:sticky lg:top-6 lg:self-start">
          <ProfileStrengthMeter completeness={completeness.data} />
          <ProfileStepper
            completeness={completeness.data}
            activeSection={activeSection}
            onSelect={setActiveSection}
          />
        </aside>

        <div className="min-w-0">
          <ActiveSection section={activeSection} />
        </div>
      </div>
    </div>
  );
}
