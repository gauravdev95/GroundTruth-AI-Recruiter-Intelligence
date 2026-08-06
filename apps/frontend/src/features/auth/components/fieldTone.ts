/**
 * Which surface a form control is sitting on.
 *
 * The same three controls — `FormField`, `PasswordInput`, `Checkbox` — are used
 * on the light bordered card that `AuthLayout` renders (forgot-password, reset-
 * password) and on the dark animated hero that `AuthHero` renders (sign in,
 * sign up). Rather than fork them, they take a `tone` and read their classes
 * from here.
 *
 * This mirrors the landing page's `ui/Button`, which already solved the same
 * problem the same way with a `tone: "light" | "dark"` prop. `light` is the
 * default everywhere, so a control that has not been told otherwise renders
 * exactly as it did before this file existed.
 *
 * ERROR TEXT IS THE ONE THING THAT DIFFERS BY MORE THAN A SHADE. `text-red-500`
 * on `#0A1128` is roughly 3.1:1 — under the 4.5:1 floor for the one piece of
 * text a user most needs to be able to read. The dark tone uses `red-300`,
 * which clears it comfortably.
 */
export type FieldTone = "light" | "dark";

interface ToneClasses {
  label: string;
  input: string;
  /** The eye toggle in `PasswordInput`, and any other in-field affordance. */
  affordance: string;
  error: string;
  /** Checkbox label copy, which sits outside the control itself. */
  checkboxLabel: string;
  checkbox: string;
}

/**
 * Focus is expressed as a ring *and* a border shift on both tones. A ring
 * alone disappears against the aurora's brighter moments; a border alone is
 * too quiet to serve as a focus indicator at all.
 */
export const FIELD_TONE: Record<FieldTone, ToneClasses> = {
  light: {
    label: "text-sm font-medium text-slate-700",
    input:
      "w-full rounded border border-slate-300 bg-white px-4 py-2.5 text-sm text-slate-900 placeholder-slate-400 outline-none transition focus:border-ink focus:ring-2 focus:ring-verified/25",
    affordance: "text-slate-400 transition hover:text-slate-700",
    error: "text-xs text-red-500",
    checkboxLabel: "flex cursor-pointer items-start gap-2.5 text-sm text-slate-600",
    checkbox:
      "mt-0.5 h-4 w-4 shrink-0 cursor-pointer rounded border-slate-300 bg-white text-verified accent-verified focus:ring-2 focus:ring-verified/30",
  },
  dark: {
    label: "text-[13px] font-medium tracking-wide text-white/70",
    input: [
      "w-full rounded-lg border border-white/15 bg-white/[0.06] px-4 py-3 text-sm text-white",
      "placeholder-white/35 outline-none backdrop-blur-sm",
      // Only `border-color`, `background-color` and `box-shadow` transition —
      // never `all`, which would also animate the text colour on autofill.
      "transition-[border-color,background-color,box-shadow] duration-200 ease-out",
      "hover:border-white/25",
      "focus:border-gt-electric focus:bg-white/[0.09] focus:ring-2 focus:ring-gt-electric/40",
    ].join(" "),
    affordance: "text-white/45 transition hover:text-white",
    error: "text-xs text-red-300",
    checkboxLabel: "flex cursor-pointer items-start gap-2.5 text-sm text-white/70",
    checkbox:
      "mt-0.5 h-4 w-4 shrink-0 cursor-pointer rounded border-white/25 bg-white/10 text-gt-electric accent-gt-electric focus:ring-2 focus:ring-gt-electric/40",
  },
};
