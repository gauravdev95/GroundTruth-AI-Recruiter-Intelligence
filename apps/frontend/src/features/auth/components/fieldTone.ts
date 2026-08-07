/**
 * Which surface a form control is sitting on.
 *
 * The same three controls — `FormField`, `PasswordInput`, `Checkbox` — are used
 * on the card that `AuthLayout` renders (forgot-password, reset-password) and
 * on the animated hero that `AuthHero` renders (sign in, sign up). Rather than
 * fork them, they take a `tone` and read their classes from here.
 *
 * This mirrors the landing page's `ui/Button`, which already solved the same
 * problem the same way with a tone prop.
 *
 * THE TONES ARE NAMED FOR THE SURFACE, NOT FOR A BRIGHTNESS. They used to be
 * `light` and `dark`, which stopped being true when the app adopted
 * `design/tokens.css`: the "light" tone is now whichever of the two themes the
 * reader has chosen, and on the default dark theme it is darker than the hero
 * it was named in contrast to. A tone called `light` that renders dark is worse
 * than no name at all.
 *
 *   app   — on the app's own surface, inside an `AuthLayout` card. Every value
 *           is a token, so this tone follows `[data-theme]` and is correct in
 *           both themes without a second class set.
 *   hero  — on `AuthHero`'s glass over the aurora. Fixed white-alpha values,
 *           deliberately NOT tokens: the hero is a dark surface in both themes
 *           because it is the landing page continued through the door, and a
 *           control there sits on the glass rather than on the app.
 *
 * ERROR TEXT IS THE ONE THING THAT DIFFERS BY MORE THAN A SHADE. `text-red-500`
 * on `#0A1128` is roughly 3.1:1 — under the 4.5:1 floor for the one piece of
 * text a user most needs to be able to read. The hero tone uses `red-300`,
 * which clears it comfortably; the app tone uses `--failed`, which is
 * re-stepped per theme and audited at 5.1:1 in the token file.
 */
export type FieldTone = "app" | "hero";

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

export const FIELD_TONE: Record<FieldTone, ToneClasses> = {
  /*
   * Kept deliberately identical to `components/Input.tsx` — recessed onto
   * `--surface`, hairline `--rule`, a border shift on focus and no ring of its
   * own, because `design/tokens.css` already draws one `:focus-visible` ring
   * for the whole product. The auth card and an app form must not be able to
   * disagree about what a text field looks like.
   */
  app: {
    label: "text-sm font-medium text-[var(--slate)]",
    input: [
      "w-full rounded-[var(--r-sm)] border border-[var(--rule)] bg-[var(--surface)] px-4 py-2.5",
      "text-sm text-[var(--ink)] placeholder:text-[var(--muted)] outline-none",
      "transition-colors duration-150 focus:border-[var(--violet)]",
      "aria-[invalid=true]:border-[var(--failed)]",
    ].join(" "),
    affordance: "text-[var(--muted)] transition-colors hover:text-[var(--ink)]",
    error: "text-xs text-[var(--failed)]",
    checkboxLabel: "flex cursor-pointer items-start gap-2.5 text-sm text-[var(--slate)]",
    checkbox:
      "mt-0.5 h-4 w-4 shrink-0 cursor-pointer rounded border-[var(--rule)] bg-[var(--surface)] text-[var(--violet)] accent-[var(--violet)]",
  },
  hero: {
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
