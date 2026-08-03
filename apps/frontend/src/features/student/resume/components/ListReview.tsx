import { Badge, Input, Select } from "@/components";

import { EMPLOYMENT_TYPE_OPTIONS } from "../../constants";
import { cn } from "@/lib/utils";

/** Draft items are shape-varied by section, so they stay loosely typed here.
 * The strict shape is enforced on submit by the section zod schemas. */
export type DraftItem = Record<string, unknown>;

export interface ListItemState<T = DraftItem> {
  included: boolean;
  value: T;
}

interface ListReviewProps {
  items: ListItemState[];
  onToggle: (index: number, included: boolean) => void;
  onChange: (index: number, next: DraftItem) => void;
  kind: "projects" | "certificates" | "experience";
  emptyMessage: string;
  itemErrors?: (string | undefined)[];
}

/**
 * Item-level review for the list sections.
 *
 * Editing is limited to the fields that decide whether an entry is usable —
 * the ones the section requires, or that determine verification (a repo URL, a
 * credential URL). Everything else the extraction found is carried through
 * unchanged, so this is a review surface rather than a second profile editor.
 */
export function ListReview({
  items,
  onToggle,
  onChange,
  kind,
  emptyMessage,
  itemErrors = [],
}: ListReviewProps) {
  if (items.length === 0) {
    return (
      <p className="rounded-xl border border-dashed border-rule bg-panel px-4 py-6 text-center text-sm text-slate-500">
        {emptyMessage}
      </p>
    );
  }

  return (
    <div className="space-y-3">
      {items.map((item, index) => {
        const value = item.value as Record<string, unknown>;
        const error = itemErrors[index];

        return (
          <div
            key={index}
            className={cn(
              "rounded-xl border p-3 transition",
              item.included ? "border-rule bg-white" : "border-dashed border-rule bg-panel/60",
            )}
          >
            <div className="mb-3 flex flex-wrap items-center gap-2">
              <label className="flex items-center gap-2 text-sm font-medium text-slate-700">
                <input
                  type="checkbox"
                  checked={item.included}
                  onChange={(event) => onToggle(index, event.target.checked)}
                  className="size-4 rounded border-slate-300 text-ink focus:ring-verified/25"
                />
                Import this entry
              </label>
              <Badge variant="info">From resume</Badge>
            </div>

            <div className={cn("space-y-3", !item.included && "pointer-events-none opacity-50")}>
              {kind === "projects" ? (
                <>
                  <Input
                    label="Title"
                    value={String(value.title ?? "")}
                    onChange={(event) => onChange(index, { title: event.target.value })}
                  />
                  <Input
                    label="Repository URL (optional)"
                    placeholder="https://github.com/you/project"
                    value={String(value.repo_url ?? "")}
                    onChange={(event) =>
                      onChange(index, {
                        repo_url: event.target.value || null,
                        kind: event.target.value ? "repository" : "described",
                      })
                    }
                  />
                </>
              ) : null}

              {kind === "certificates" ? (
                <>
                  <div className="grid gap-3 sm:grid-cols-2">
                    <Input
                      label="Title"
                      value={String(value.title ?? "")}
                      onChange={(event) =>
                        onChange(index, { title: event.target.value })
                      }
                    />
                    <Input
                      label="Issuer"
                      value={String(value.issuer ?? "")}
                      onChange={(event) =>
                        onChange(index, { issuer: event.target.value })
                      }
                    />
                  </div>
                  <Input
                    label="Credential URL (optional)"
                    placeholder="https://credly.com/badges/..."
                    value={String(value.credential_url ?? "")}
                    onChange={(event) =>
                      onChange(index, {
                        credential_url: event.target.value || null,
                      })
                    }
                  />
                </>
              ) : null}

              {kind === "experience" ? (
                <>
                  <div className="grid gap-3 sm:grid-cols-2">
                    <Input
                      label="Company"
                      value={String(value.company_name ?? "")}
                      onChange={(event) =>
                        onChange(index, { company_name: event.target.value })
                      }
                    />
                    <Input
                      label="Role"
                      value={String(value.title ?? "")}
                      onChange={(event) =>
                        onChange(index, { title: event.target.value })
                      }
                    />
                  </div>
                  <div className="grid gap-3 sm:grid-cols-3">
                    <Select
                      label="Type"
                      options={EMPLOYMENT_TYPE_OPTIONS}
                      value={String(value.employment_type ?? "internship")}
                      onChange={(event) =>
                        onChange(index, { employment_type: event.target.value })
                      }
                    />
                    <Input
                      type="date"
                      label="Start date"
                      value={String(value.start_date ?? "")}
                      onChange={(event) =>
                        onChange(index, { start_date: event.target.value })
                      }
                    />
                    <Input
                      type="date"
                      label="End date"
                      value={String(value.end_date ?? "")}
                      onChange={(event) =>
                        onChange(index, {
                          end_date: event.target.value || null,
                        })
                      }
                    />
                  </div>
                  {!value.start_date ? (
                    <p className="text-xs text-flagged">
                      A start date is required — the resume didn&apos;t give a readable one.
                    </p>
                  ) : null}
                </>
              ) : null}
            </div>

            {error ? (
              <p role="alert" className="mt-2 text-xs text-red-500">
                {error}
              </p>
            ) : null}
          </div>
        );
      })}
    </div>
  );
}
