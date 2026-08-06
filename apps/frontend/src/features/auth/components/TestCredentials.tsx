import { Check, Copy } from "lucide-react";
import { useState } from "react";

/**
 * The seeded demo logins, shown on `/login` in development only.
 *
 * ## Why this is gated on `import.meta.env.DEV` and not on a flag
 *
 * A panel listing working credentials is a production incident, not a
 * feature. `import.meta.env.DEV` is resolved by Vite at build time and the
 * whole subtree is dead-code-eliminated from the production bundle, so the
 * strings below are not merely hidden in the built app — they are not in it.
 * A runtime flag would ship them and rely on a condition being right forever.
 *
 * ## The password
 *
 * `Test1234!`, not the `test1234` the demo brief specifies:
 * `auth/schemas.py::_validate_password_strength` requires an uppercase letter
 * and a special character, so `test1234` cannot be registered at all. Keep
 * this string in step with `scripts/seed_demo.py::DEMO_PASSWORD` — they are
 * the two ends of one fact, and there is no import that can join a Python
 * constant to a TypeScript one.
 */
const DEMO_PASSWORD = "Test1234!";

const RECRUITER = { email: "recruiter@test.com", label: "Deepak Verma · TechNova Solutions" };

const STUDENTS = [
  { email: "rahul@test.com", label: "Rahul Sharma · Rust, PostgreSQL, distributed systems" },
  { email: "roshni@test.com", label: "Roshni Iyer · Rust, WebAssembly, systems" },
  { email: "arjun@test.com", label: "Arjun Mehta · Go, Kubernetes, CI/CD" },
  { email: "vikram@test.com", label: "Vikram Singh · Java, Spring Boot" },
  { email: "meera@test.com", label: "Meera Krishnan · Node.js, MongoDB, AWS" },
  { email: "priya@test.com", label: "Priya Patel · React, TypeScript, Node.js" },
  { email: "sneha@test.com", label: "Sneha Gupta · Python, ML, TensorFlow" },
  { email: "karan@test.com", label: "Karan Joshi · C++, algorithms" },
  { email: "ananya@test.com", label: "Ananya Reddy · React, Next.js (no backend match)" },
  { email: "aditya@test.com", label: "Aditya Chauhan · Flutter, Dart (no backend match)" },
] as const;

function CopyRow({ value, label }: { value: string; label: string }) {
  const [copied, setCopied] = useState(false);

  const copy = () => {
    void navigator.clipboard?.writeText(value).then(() => {
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1200);
    });
  };

  return (
    <li className="flex items-center justify-between gap-3 py-1">
      <span className="min-w-0">
        <button
          type="button"
          onClick={copy}
          className="inline-flex items-center gap-1.5 font-mono text-[11px] text-white/85 transition hover:text-white"
          aria-label={`Copy ${value}`}
        >
          {value}
          {copied ? (
            <Check size={10} className="text-emerald-400" aria-hidden="true" />
          ) : (
            <Copy size={10} className="opacity-40" aria-hidden="true" />
          )}
        </button>
        <span className="ml-2 truncate text-[10px] text-white/35">{label}</span>
      </span>
    </li>
  );
}

export function TestCredentials() {
  const [open, setOpen] = useState(false);

  if (!import.meta.env.DEV) return null;

  return (
    <div className="mt-6 rounded-xl border border-white/10 bg-white/[0.03] p-4">
      <div className="flex items-center justify-between gap-3">
        <p className="text-[10px] font-semibold uppercase tracking-widest text-white/45">
          Test accounts · development only
        </p>
        <button
          type="button"
          onClick={() => setOpen((value) => !value)}
          aria-expanded={open}
          className="text-[10px] font-medium uppercase tracking-wide text-white/50 transition hover:text-white/80"
        >
          {open ? "Hide" : "Show all"}
        </button>
      </div>

      <p className="mt-2 text-[11px] text-white/50">
        Password for every account:{" "}
        <span className="font-mono text-white/85">{DEMO_PASSWORD}</span>
      </p>

      <ul className="mt-2 border-t border-white/10 pt-2">
        <CopyRow value={RECRUITER.email} label={RECRUITER.label} />
      </ul>

      <ul className="mt-1 border-t border-white/10 pt-2">
        {/* Two students by default — Rahul is the one the demo script follows
            and Ananya is the one who deliberately does not match, which is
            worth being able to check without expanding. */}
        {(open ? STUDENTS : [STUDENTS[0], STUDENTS[STUDENTS.length - 2]]).map((student) => (
          <CopyRow key={student.email} value={student.email} label={student.label} />
        ))}
      </ul>
    </div>
  );
}
