import { Globe, Target, X } from "lucide-react";

import { Button, Input, Select, type SelectOption } from "@/components";
import { Surface } from "@/design/Surface";
import { cn } from "@/lib/utils";

import type { FeedFilterState, FeedSort } from "../lib/feedFilters";
import { isDefaultFilters } from "../lib/feedFilters";

const SORT_OPTIONS: SelectOption[] = [
  { value: "best", label: "Best match" },
  { value: "closing", label: "Closing soon" },
  { value: "newest", label: "Newest match" },
];

function FilterToggle({
  pressed,
  onToggle,
  icon,
  label,
}: {
  pressed: boolean;
  onToggle: () => void;
  icon: React.ReactNode;
  label: string;
}) {
  return (
    <button
      type="button"
      aria-pressed={pressed}
      onClick={onToggle}
      className={cn(
        "inline-flex min-h-10 items-center gap-1.5 rounded-[var(--r-sm)] border px-3 text-[13px] font-medium transition-colors duration-150",
        pressed
          ? "border-[var(--violet)]/40 bg-[var(--violet)]/12 text-[var(--violet)]"
          : "border-[var(--rule)] bg-[var(--surface)] text-[var(--slate)] hover:text-[var(--ink)]",
      )}
    >
      {icon}
      {label}
    </button>
  );
}

/**
 * Search and filters for the job feed, in one card above the list.
 *
 * Every control maps to a dimension the feed payload carries — the feed
 * endpoint itself takes no query parameters, so these filter the returned
 * rows client-side (`matches/lib/feedFilters.ts`). The option lists are
 * built from the values actually present in this feed, so a filter can
 * never offer a choice that matches nothing by construction.
 *
 * The two toggles are `aria-pressed` buttons, not checkboxes: they read as
 * filter chips, and a chip that is on is violet, never green — toggles are
 * UI state, and rule 1 forbids spending green on it.
 */
export function JobFeedFilters({
  filters,
  onChange,
  jobTypeOptions,
  experienceOptions,
}: {
  filters: FeedFilterState;
  onChange: (next: FeedFilterState) => void;
  jobTypeOptions: SelectOption[];
  experienceOptions: SelectOption[];
}) {
  const set = (patch: Partial<FeedFilterState>) => onChange({ ...filters, ...patch });

  return (
    <Surface className="p-4 sm:p-5">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-[2fr_1fr_1fr_1fr]">
        <Input
          label="Search jobs"
          type="search"
          placeholder="Title, company, location or skill"
          value={filters.query}
          onChange={(event) => set({ query: event.target.value })}
        />
        <Select
          label="Job type"
          options={[{ value: "all", label: "All types" }, ...jobTypeOptions]}
          value={filters.jobType}
          onChange={(event) => set({ jobType: event.target.value })}
        />
        <Select
          label="Experience"
          options={[{ value: "all", label: "Any experience" }, ...experienceOptions]}
          value={filters.experience}
          onChange={(event) => set({ experience: event.target.value })}
        />
        <Select
          label="Sort by"
          options={SORT_OPTIONS}
          value={filters.sort}
          onChange={(event) => set({ sort: event.target.value as FeedSort })}
        />
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-2">
        <FilterToggle
          pressed={filters.remoteOnly}
          onToggle={() => set({ remoteOnly: !filters.remoteOnly })}
          icon={<Globe size={14} aria-hidden="true" />}
          label="Remote only"
        />
        <FilterToggle
          pressed={filters.highMatchOnly}
          onToggle={() => set({ highMatchOnly: !filters.highMatchOnly })}
          icon={<Target size={14} aria-hidden="true" />}
          label="High match only"
        />
        {!isDefaultFilters(filters) ? (
          <Button
            variant="ghost"
            size="sm"
            onClick={() =>
              onChange({
                query: "",
                jobType: "all",
                experience: "all",
                remoteOnly: false,
                highMatchOnly: false,
                sort: "best",
              })
            }
          >
            <X size={14} aria-hidden="true" />
            Clear filters
          </Button>
        ) : null}
      </div>
    </Surface>
  );
}
