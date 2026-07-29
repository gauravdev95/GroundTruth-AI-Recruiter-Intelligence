import { Briefcase, Search, X } from "lucide-react";
import { useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";

interface RoleSelectModalProps {
  open: boolean;
  onClose: () => void;
}

const FOCUSABLE_SELECTOR =
  'a[href], button:not([disabled]), textarea, input, select, [tabindex]:not([tabindex="-1"])';

export function RoleSelectModal({ open, onClose }: RoleSelectModalProps) {
  const navigate = useNavigate();
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

  const goTo = (path: string) => {
    onClose();
    navigate(path);
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 px-4 backdrop-blur-sm animate-fade-in"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="role-select-title"
        className="relative w-full max-w-lg animate-scale-in rounded-3xl border border-slate-200 bg-white p-7 shadow-2xl shadow-slate-900/20 sm:p-9"
      >
        <button
          type="button"
          onClick={onClose}
          aria-label="Close"
          className="absolute right-5 top-5 text-slate-400 transition hover:text-slate-700"
        >
          <X size={18} />
        </button>

        <h2 id="role-select-title" className="text-center text-xl font-semibold tracking-tight text-slate-900">
          Who are you?
        </h2>
        <p className="mt-1.5 text-center text-sm text-slate-500">Pick a path to continue to GroundTruth AI.</p>

        <div className="mt-7 grid gap-4 sm:grid-cols-2">
          <button
            type="button"
            onClick={() => goTo("/login/candidate")}
            className="group relative overflow-hidden rounded-2xl border border-slate-200 bg-white p-6 text-left shadow-sm transition duration-300 hover:-translate-y-1 hover:border-indigo-300 hover:shadow-xl hover:shadow-indigo-500/10"
          >
            <div className="absolute -right-6 -top-6 h-24 w-24 rounded-full bg-indigo-500/5 blur-2xl transition group-hover:bg-indigo-500/15" />
            <div className="relative flex h-11 w-11 items-center justify-center rounded-xl bg-gradient-to-br from-[#4F46E5] to-[#7C3AED] text-white shadow-lg shadow-indigo-500/25">
              <Search size={20} />
            </div>
            <div className="relative mt-4">
              <div className="font-semibold text-slate-900">Find a Job</div>
              <div className="mt-1 text-sm text-slate-500">Candidate / Student</div>
            </div>
          </button>

          <button
            type="button"
            onClick={() => goTo("/login/recruiter")}
            className="group relative overflow-hidden rounded-2xl border border-slate-200 bg-white p-6 text-left shadow-sm transition duration-300 hover:-translate-y-1 hover:border-violet-300 hover:shadow-xl hover:shadow-violet-500/10"
          >
            <div className="absolute -right-6 -top-6 h-24 w-24 rounded-full bg-violet-500/5 blur-2xl transition group-hover:bg-violet-500/15" />
            <div className="relative flex h-11 w-11 items-center justify-center rounded-xl bg-gradient-to-br from-[#7C3AED] to-[#4F46E5] text-white shadow-lg shadow-violet-500/25">
              <Briefcase size={20} />
            </div>
            <div className="relative mt-4">
              <div className="font-semibold text-slate-900">Hire Talent</div>
              <div className="mt-1 text-sm text-slate-500">Recruiter</div>
            </div>
          </button>
        </div>
      </div>
    </div>
  );
}
