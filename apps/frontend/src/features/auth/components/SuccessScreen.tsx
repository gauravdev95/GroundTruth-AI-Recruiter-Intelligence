import { CheckCircle2 } from "lucide-react";
import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

import type { FieldTone } from "./fieldTone";

interface SuccessScreenProps {
  title: string;
  description?: string;
  children?: ReactNode;
  /** Which surface this sits on. See `fieldTone.ts`. */
  tone?: FieldTone;
}

export function SuccessScreen({ title, description, children, tone = "app" }: SuccessScreenProps) {
  const hero = tone === "hero";

  return (
    <div className="flex flex-col items-center gap-4 py-2 text-center animate-fade-in">
      {/*
        Green here is `--verified` used as *light around a completed action*,
        not as a claim about evidence — the same narrow exemption the
        celebration burst gets in `design/primitives.tsx`. It is a tint behind
        an icon on a screen that makes no claim about a student's skills, and
        it never appears beside an unproven badge.

        On the hero the app token cannot be used: `--verified` is re-stepped
        per theme and its light-theme value is too dark for the hero's dark
        glass in a light-theme session. Emerald-300 is the same hue, fixed
        for a dark surface.
      */}
      <div
        className={cn(
          "flex h-14 w-14 items-center justify-center rounded-full animate-scale-in",
          hero
            ? "bg-emerald-400/15 text-emerald-300"
            : "bg-[var(--verified)]/12 text-[var(--verified)]",
        )}
      >
        <CheckCircle2 size={30} strokeWidth={1.75} />
      </div>
      <div>
        <h2
          className={cn(
            "font-display text-lg font-semibold",
            hero ? "text-white" : "text-[var(--ink)]",
          )}
        >
          {title}
        </h2>
        {description ? (
          <p className={cn("mt-1.5 text-sm", hero ? "text-white/60" : "text-[var(--slate)]")}>
            {description}
          </p>
        ) : null}
      </div>
      {children}
    </div>
  );
}
