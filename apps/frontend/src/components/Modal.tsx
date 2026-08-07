import { X } from "lucide-react";
import { useEffect, useRef } from "react";
import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

export interface ModalProps {
  open: boolean;
  onClose: () => void;
  title?: string;
  children: ReactNode;
  className?: string;
}

const FOCUSABLE_SELECTOR =
  'a[href], button:not([disabled]), textarea, input, select, [tabindex]:not([tabindex="-1"])';

/** Same focus-trap/escape-key/scroll-lock behavior as
 * `features/auth/components/RoleSelectModal.tsx`, generalized for reuse
 * outside auth. */
export function Modal({ open, onClose, title, children, className }: ModalProps) {
  const dialogRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<Element | null>(null);

  useEffect(() => {
    if (!open) return;

    triggerRef.current = document.activeElement;
    const dialog = dialogRef.current;
    const focusable = dialog?.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR);
    focusable?.[0]?.focus();

    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
        return;
      }
      if (e.key !== "Tab" || !focusable || focusable.length === 0) return;

      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    };

    document.addEventListener("keydown", onKeyDown);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.body.style.overflow = "";
      (triggerRef.current as HTMLElement | null)?.focus?.();
    };
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex animate-fade-in items-center justify-center bg-[var(--scrim)] px-4 backdrop-blur-sm"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      {/*
        `--panel-raised` and opaque, matching `Surface`'s `floating` elevation.
        A modal can land over arbitrary scrolled content, and the translucency
        that makes a `--panel` card feel light makes a dialog unreadable — the
        text competes with whatever happens to be beneath it. The scrim already
        supplies the depth.
      */}
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={title ? "modal-title" : undefined}
        className={cn(
          "relative w-full max-w-md animate-scale-in rounded-[var(--r-xl)] border border-[var(--rule)] bg-[var(--panel-raised)] p-7 shadow-[var(--shadow-raised)]",
          className,
        )}
      >
        <button
          type="button"
          onClick={onClose}
          aria-label="Close"
          className="absolute right-5 top-5 rounded-[var(--r-sm)] text-[var(--muted)] transition-colors hover:text-[var(--ink)]"
        >
          <X size={18} />
        </button>

        {title ? (
          <h2
            id="modal-title"
            className="pr-8 font-display text-lg font-semibold tracking-tight text-[var(--ink)]"
          >
            {title}
          </h2>
        ) : null}

        <div className={title ? "mt-4" : undefined}>{children}</div>
      </div>
    </div>
  );
}
