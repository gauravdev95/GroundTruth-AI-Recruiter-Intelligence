import { AlertTriangle } from "lucide-react";
import type { ReactNode } from "react";

import { Button } from "./Button";
import { Modal } from "./Modal";

export interface ConfirmDialogProps {
  open: boolean;
  onClose: () => void;
  /** Called when the user confirms. The dialog does not close itself first —
   * the caller closes it after its action completes, so a failing action
   * does not leave the user staring at a closed dialog and no feedback. */
  onConfirm: () => void;
  title: string;
  description?: string;
  confirmLabel?: string;
  cancelLabel?: string;
  /** `danger` renders the confirm button and the icon in `--failed` for
   * irreversible actions (withdraw, delete, reject). `default` is for
   * reversible confirmations (leave this page, discard a draft). */
  tone?: "default" | "danger";
  isConfirming?: boolean;
  children?: ReactNode;
}

/**
 * The "are you sure" dialog, built on `Modal` so it inherits the focus
 * trap, Escape handling, scrim and scroll lock rather than re-implementing
 * them — a confirmation dialog that does not trap focus is a dialog that
 * lets a keyboard user confirm something they cannot see.
 *
 * The confirm action is the only button in the product that is allowed to
 * be destructive by default: `tone="danger"` is explicit at the call site,
 * so a reviewer can see from the props whether the dialog destroys
 * something. The cancel button is always `secondary` and always first in
 * the DOM after the description, so the safe action is the one a Tab reaches
 * first.
 */
export function ConfirmDialog({
  open,
  onClose,
  onConfirm,
  title,
  description,
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  tone = "default",
  isConfirming = false,
  children,
}: ConfirmDialogProps) {
  return (
    <Modal open={open} onClose={onClose} title={title}>
      <div className="flex flex-col gap-4">
        {tone === "danger" ? (
          <div className="flex h-11 w-11 items-center justify-center rounded-full bg-[var(--failed)]/12 text-[var(--failed)]">
            <AlertTriangle size={20} aria-hidden="true" />
          </div>
        ) : null}
        {description ? <p className="text-sm leading-relaxed text-[var(--slate)]">{description}</p> : null}
        {children}
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={onClose} disabled={isConfirming}>
            {cancelLabel}
          </Button>
          <Button
            variant={tone === "danger" ? "danger" : "primary"}
            onClick={onConfirm}
            isLoading={isConfirming}
          >
            {confirmLabel}
          </Button>
        </div>
      </div>
    </Modal>
  );
}
