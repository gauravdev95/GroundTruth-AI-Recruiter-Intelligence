import { AlertCircle, CheckCircle2, Info, X } from "lucide-react";
import { createContext, useCallback, useContext, useState } from "react";
import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

export type ToastVariant = "success" | "error" | "info";

interface ToastItem {
  id: string;
  message: string;
  variant: ToastVariant;
}

interface ToastContextValue {
  showToast: (message: string, variant?: ToastVariant) => void;
}

const ToastContext = createContext<ToastContextValue | undefined>(undefined);

/**
 * Toasts are opaque `--panel-raised`, like every other floating surface, with
 * the status colour carried by the icon and a left edge rather than by a fill.
 * A toast lands over whatever the user was reading, so a translucent one is
 * unreadable — and a fully tinted one at this size is a coloured slab across
 * the top of the screen.
 *
 * ON `success` BEING GREEN. The token file's rule 1 reserves `--verified` for
 * "proven by an artefact", and a toast saying "Job created" proves nothing. It
 * is allowed here under the same exemption the celebration burst gets: a toast
 * is unattached to any claim, it is transient, and it never appears beside an
 * unproven one. What it must never become is a *badge* — if a persistent chip
 * ever needs to say "saved", that is `neutral`, not this.
 */
const VARIANT_STYLES: Record<ToastVariant, string> = {
  success: "border-[var(--rule)] border-l-[var(--verified)] text-[var(--ink)]",
  error: "border-[var(--rule)] border-l-[var(--failed)] text-[var(--ink)]",
  info: "border-[var(--rule)] border-l-[var(--blue)] text-[var(--ink)]",
};

const VARIANT_ICON_TONE: Record<ToastVariant, string> = {
  success: "text-[var(--verified)]",
  error: "text-[var(--failed)]",
  info: "text-[var(--blue)]",
};

const VARIANT_ICONS: Record<ToastVariant, typeof Info> = {
  success: CheckCircle2,
  error: AlertCircle,
  info: Info,
};

const AUTO_DISMISS_MS = 5000;

/** Mounted once near the root (see `app/App.tsx`); call `useToast().showToast(...)`
 * from anywhere below it. */
export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const dismiss = useCallback((id: string) => {
    setToasts((current) => current.filter((toast) => toast.id !== id));
  }, []);

  const showToast = useCallback(
    (message: string, variant: ToastVariant = "info") => {
      const id = crypto.randomUUID();
      setToasts((current) => [...current, { id, message, variant }]);
      window.setTimeout(() => dismiss(id), AUTO_DISMISS_MS);
    },
    [dismiss],
  );

  return (
    <ToastContext.Provider value={{ showToast }}>
      {children}
      <div className="pointer-events-none fixed inset-x-0 top-4 z-[100] flex flex-col items-center gap-2 px-4">
        {toasts.map((toast) => {
          const Icon = VARIANT_ICONS[toast.variant];
          return (
            <div
              key={toast.id}
              role="status"
              className={cn(
                "pointer-events-auto flex w-full max-w-sm animate-slide-up items-start gap-2.5 rounded-[var(--r-md)] border border-l-2 bg-[var(--panel-raised)] p-3 text-sm shadow-[var(--shadow-raised)]",
                VARIANT_STYLES[toast.variant],
              )}
            >
              <Icon
                size={18}
                aria-hidden="true"
                className={cn("mt-0.5 shrink-0", VARIANT_ICON_TONE[toast.variant])}
              />
              <p className="flex-1">{toast.message}</p>
              <button
                type="button"
                onClick={() => dismiss(toast.id)}
                aria-label="Dismiss"
                className="shrink-0 rounded-[var(--r-sm)] text-[var(--muted)] transition-colors hover:text-[var(--ink)]"
              >
                <X size={14} />
              </button>
            </div>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext);
  if (!ctx) {
    throw new Error("useToast must be used within a ToastProvider");
  }
  return ctx;
}
