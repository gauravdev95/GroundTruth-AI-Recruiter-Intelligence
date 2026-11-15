import { Moon, Sun } from "lucide-react";

import { useTheme } from "@/design/theme";

import { Button } from "./Button";

/**
 * The theme toggle. An icon button that flips dark ↔ light through
 * `useTheme`, which writes `[data-theme]` on `<html>` and persists the
 * choice — the explicit choice the token file requires to win over
 * `prefers-color-scheme`.
 *
 * The icon shows the theme you will get, not the one you are in: a sun on a
 * dark page means "switch to light". The label says the same thing in words,
 * so the control does not depend on the icon being read correctly.
 *
 * NOT wired into any shell yet. Later phases place it in the dashboard
 * header (and the landing nav, if the brief asks for one there); this
 * component is the control, and placement is a layout decision that belongs
 * to the phase that owns the shell.
 */
export function ThemeToggle({ className }: { className?: string }) {
  const { resolved, toggleTheme } = useTheme();
  const isDark = resolved === "dark";

  return (
    <Button
      type="button"
      variant="ghost"
      size="icon"
      onClick={toggleTheme}
      aria-label={isDark ? "Switch to light theme" : "Switch to dark theme"}
      title={isDark ? "Switch to light theme" : "Switch to dark theme"}
      className={className}
    >
      {isDark ? <Sun size={18} aria-hidden="true" /> : <Moon size={18} aria-hidden="true" />}
    </Button>
  );
}
