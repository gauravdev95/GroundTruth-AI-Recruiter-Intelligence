import { useCallback, useEffect, useState } from "react";

/**
 * Theme state — the JS half of the `[data-theme]` contract in
 * `design/tokens.css`.
 *
 * The CSS already resolves the theme with this precedence: an explicit
 * `[data-theme]` on `<html>` wins over `prefers-color-scheme`, and the
 * media query only applies when no explicit choice exists
 * (`:root:not([data-theme])`). This hook is the only writer of that
 * attribute, and the only reader of the persisted choice, so the two halves
 * cannot disagree about what "explicit" means.
 *
 * Three states, not two. `system` means "no explicit choice": the attribute
 * is removed and the OS decides through the media query, exactly as it does
 * for a first-time visitor. `dark` / `light` write the attribute and persist.
 * A toggle that only flipped dark ↔ light would strand a user who had
 * explicitly chosen one and then wanted the OS to decide again.
 *
 * Nothing in the app wires this into a UI yet — `ThemeToggle` (components)
 * is the control, and later phases place it in the shell. This module is
 * hook-only on purpose: the `react-refresh/only-export-components` rule
 * warns on files that mix components and hooks.
 */

export type ThemeChoice = "dark" | "light" | "system";

export type ResolvedTheme = "dark" | "light";

const STORAGE_KEY = "gt-theme";

function readStoredChoice(): ThemeChoice {
  if (typeof window === "undefined") return "system";
  const stored = window.localStorage.getItem(STORAGE_KEY);
  return stored === "dark" || stored === "light" || stored === "system" ? stored : "system";
}

function systemTheme(): ResolvedTheme {
  if (typeof window === "undefined") return "dark";
  return window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
}

/** The theme the page actually renders in, for a given explicit choice. */
export function resolveTheme(choice: ThemeChoice): ResolvedTheme {
  return choice === "system" ? systemTheme() : choice;
}

/**
 * Applies a choice to the document: writes or removes `[data-theme]` and
 * persists it. Safe to call outside React (e.g. an inline script that runs
 * before the bundle to avoid a theme flash) — it touches only
 * `document.documentElement` and `localStorage`.
 */
export function applyTheme(choice: ThemeChoice): void {
  if (typeof document === "undefined") return;
  if (choice === "system") {
    document.documentElement.removeAttribute("data-theme");
  } else {
    document.documentElement.setAttribute("data-theme", choice);
  }
  try {
    window.localStorage.setItem(STORAGE_KEY, choice);
  } catch {
    // Private mode or a blocked store: the attribute is already applied for
    // this session, so the choice still holds until the tab closes.
  }
}

export interface UseThemeResult {
  /** The explicit choice, or "system" when the OS decides. */
  theme: ThemeChoice;
  /** The theme the page is actually rendering in right now. */
  resolved: ResolvedTheme;
  setTheme: (choice: ThemeChoice) => void;
  /** Flips dark ↔ light, ignoring "system" — the control's one job. */
  toggleTheme: () => void;
}

export function useTheme(): UseThemeResult {
  const [theme, setThemeState] = useState<ThemeChoice>(readStoredChoice);
  const [resolved, setResolved] = useState<ResolvedTheme>(() => resolveTheme(readStoredChoice()));

  useEffect(() => {
    applyTheme(theme);
    setResolved(resolveTheme(theme));
  }, [theme]);

  // When the choice is "system", the OS can change its mind mid-session
  // (sunset, a schedule). Re-resolve on the media query changing; when the
  // choice is explicit there is nothing to re-resolve.
  useEffect(() => {
    if (theme !== "system") return;
    const list = window.matchMedia("(prefers-color-scheme: light)");
    const onChange = () => setResolved(resolveTheme("system"));
    list.addEventListener("change", onChange);
    return () => list.removeEventListener("change", onChange);
  }, [theme]);

  const setTheme = useCallback((choice: ThemeChoice) => {
    setThemeState(choice);
  }, []);

  const toggleTheme = useCallback(() => {
    setThemeState((current) =>
      resolveTheme(current) === "dark" ? "light" : "dark",
    );
  }, []);

  return { theme, resolved, setTheme, toggleTheme };
}
