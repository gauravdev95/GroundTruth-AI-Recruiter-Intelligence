import type { HTMLAttributes } from "react";

import { cn } from "@/lib/utils";

export function Skeleton({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      aria-hidden="true"
      className={cn(
        "animate-shimmer rounded-lg bg-[length:200%_100%] bg-gradient-to-r from-slate-100 via-slate-200 to-slate-100",
        className,
      )}
      {...props}
    />
  );
}
