import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

/**
 * The frame shared by the two product mockups — the engineer's evidence report
 * and the recruiter's pipeline board.
 *
 * They were built separately and drifted: different padding, different border
 * weights, and a shadow on one but not the other. Side by side down the page
 * that reads as two components borrowed from two design systems, which is
 * exactly the impression a product claiming auditable consistency cannot
 * afford. Both now come through here, so the radius, the shadow, the tilt and
 * the caption chip are defined once and cannot diverge again.
 *
 * The tilt alternates by side and is applied only where a pointer exists: on a
 * desktop it reads as a physical card, on a phone there is no depth cue to
 * explain it and it just looks like a crooked screenshot.
 *
 * `shadow` is the brief's ceiling — `0 4px 24px rgba(0,0,0,0.08)` — and it is
 * kept on the dark variant too even though it is nearly invisible there. The
 * point is that one value governs both; a card that drops its shadow because
 * the background hides it is how the two got out of step the first time.
 */
export function MockCard({
  tone,
  tilt,
  caption,
  title,
  children,
}: {
  tone: "light" | "dark";
  /** Which way the card leans on desktop. The two mockups lean apart. */
  tilt: "left" | "right";
  /** The sample-data label. Never optional — see the note in `landing.ts`. */
  caption: string;
  title: ReactNode;
  children: ReactNode;
}) {
  return (
    <div
      className={cn(
        "rounded-2xl border p-6 shadow-[0_4px_24px_rgba(0,0,0,0.08)] md:p-8",
        tone === "light" ? "border-black/[0.08] bg-white" : "border-white/10 bg-white/[0.04]",
        tilt === "left" ? "md:rotate-[-1.5deg]" : "md:rotate-[1.5deg]",
      )}
    >
      <div className="flex items-start justify-between gap-4">
        {title}
        <span
          className={cn(
            "shrink-0 rounded-md border px-2.5 py-1 font-mono text-[10px] uppercase tracking-wider",
            tone === "light"
              ? "border-black/10 bg-black/[0.03] text-gt-slate"
              : "border-white/15 bg-white/5 text-gt-ash",
          )}
        >
          {caption}
        </span>
      </div>

      {children}
    </div>
  );
}
