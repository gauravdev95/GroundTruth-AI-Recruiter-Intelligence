import { Check } from "lucide-react";

import { cn } from "@/lib/utils";

import type { TargetRoleType } from "../api/profileApi";
import { TARGET_ROLE_OPTIONS } from "../constants";

const MAX_ROLES = 3;

interface TargetRolesFieldProps {
  value: TargetRoleType[];
  onChange: (roles: TargetRoleType[]) => void;
  error?: string;
}

/**
 * One to three target roles, as toggle chips.
 *
 * **Chips rather than a multi-select listbox** because the whole option set is
 * eleven items and fits on screen: a native multi-select hides the choices
 * behind a click and makes "how many have I picked" invisible, which is the
 * one thing a field with a hard maximum has to keep visible.
 *
 * **Order is preserved and is meaningful.** The first role picked becomes the
 * profile's primary `target_role` — the one the matcher indexes and the one
 * recruiter-facing surfaces display — so selection appends rather than
 * re-sorting into option order, and the primary chip says so. Re-sorting would
 * silently change which role the student is matched on first.
 *
 * At the cap, unpicked chips are disabled rather than hidden. A student who
 * has chosen three and wants a fourth needs to see what they would be trading
 * away; hiding the rest turns a full field into an empty-looking one.
 */
export function TargetRolesField({ value, onChange, error }: TargetRolesFieldProps) {
  const atCap = value.length >= MAX_ROLES;

  function toggle(role: TargetRoleType) {
    if (value.includes(role)) {
      onChange(value.filter((item) => item !== role));
      return;
    }
    if (atCap) return;
    onChange([...value, role]);
  }

  return (
    <fieldset className="flex flex-col gap-2">
      <legend className="mb-1.5 text-sm font-medium text-[var(--slate)]">
        Target roles{" "}
        <span className="font-normal text-[var(--muted)]">
          — pick 1 to {MAX_ROLES}
        </span>
      </legend>

      <div className="flex flex-wrap gap-2">
        {TARGET_ROLE_OPTIONS.map((option) => {
          const role = option.value as TargetRoleType;
          const index = value.indexOf(role);
          const selected = index >= 0;
          const disabled = !selected && atCap;

          return (
            <button
              key={role}
              type="button"
              onClick={() => toggle(role)}
              disabled={disabled}
              aria-pressed={selected}
              className={cn(
                "inline-flex items-center gap-1.5 rounded-full border px-3.5 py-1.5 text-sm transition",
                selected
                  ? "border-[var(--rule)] bg-[var(--violet)] text-white"
                  : "border-[var(--rule)] bg-[var(--panel)] text-[var(--slate)] hover:border-[var(--slate)]",
                disabled && "cursor-not-allowed opacity-40 hover:border-[var(--rule)]",
              )}
            >
              {selected ? <Check size={13} strokeWidth={3} aria-hidden="true" /> : null}
              {option.label}
              {index === 0 ? (
                <span className="ml-0.5 rounded-full bg-[var(--panel)]/20 px-1.5 text-[10px] font-semibold uppercase tracking-wide">
                  Primary
                </span>
              ) : null}
            </button>
          );
        })}
      </div>

      <p className="text-xs text-[var(--slate)]">
        {value.length === 0
          ? "Your first pick becomes your primary role — it's the one recruiters see first."
          : `${value.length} of ${MAX_ROLES} selected. Primary: ${
              TARGET_ROLE_OPTIONS.find((option) => option.value === value[0])?.label ?? value[0]
            }.`}
      </p>

      {error ? (
        <p role="alert" className="text-xs text-rejected">
          {error}
        </p>
      ) : null}
    </fieldset>
  );
}
