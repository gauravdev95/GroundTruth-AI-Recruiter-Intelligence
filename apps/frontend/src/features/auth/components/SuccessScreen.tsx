import { CheckCircle2 } from "lucide-react";
import type { ReactNode } from "react";

interface SuccessScreenProps {
  title: string;
  description?: string;
  children?: ReactNode;
}

export function SuccessScreen({ title, description, children }: SuccessScreenProps) {
  return (
    <div className="flex flex-col items-center gap-4 py-2 text-center animate-fade-in">
      {/*
        Green here is `--verified` used as *light around a completed action*,
        not as a claim about evidence — the same narrow exemption the
        celebration burst gets in `design/primitives.tsx`. It is a tint behind
        an icon on a screen that makes no claim about a student's skills, and
        it never appears beside an unproven badge.
      */}
      <div className="flex h-14 w-14 items-center justify-center rounded-full bg-[var(--verified)]/12 text-[var(--verified)] animate-scale-in">
        <CheckCircle2 size={30} strokeWidth={1.75} />
      </div>
      <div>
        <h2 className="font-display text-lg font-semibold text-[var(--ink)]">{title}</h2>
        {description ? (
          <p className="mt-1.5 text-sm text-[var(--slate)]">{description}</p>
        ) : null}
      </div>
      {children}
    </div>
  );
}
