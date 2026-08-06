import {
  AlertTriangle,
  ArrowRight,
  BadgeCheck,
  ExternalLink,
  MessageSquare,
  MoreHorizontal,
  X,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";

import { Button, ErrorState, Skeleton } from "@/components";
import { SkillRadar } from "@/components/charts/SkillRadar";
import { cn } from "@/lib/utils";

import { MatchScore } from "../../components/MatchScore";
import type { EvidenceRecord, EvidenceSkillReason } from "../api/evidenceApi";
import { useCandidateEvidence } from "../hooks/useEvidence";
import { ActivityTab, InterviewTab } from "./evidenceTabs";
import { buildRadarAxes } from "./radarAxes";

/** The drawer's three views. `Evidence` is the default because it is the one
 * that answers "should I keep reading" — the other two are follow-ups. */
const TABS = ["Evidence", "Interview", "Activity"] as const;
type DrawerTab = (typeof TABS)[number];

/* ==================================================================
   SECTION 2 — VERIFIED SKILLS
   ================================================================== */

/**
 * The evidence bar, identical in construction to the one the candidate sees
 * on their own profile (`student/interview/components/EvidenceReportView.tsx`).
 * Same 6px track, same `--verified` fill, same right-aligned percentage.
 *
 * That sameness is load-bearing, not cosmetic. A student who reads "Rust 82%,
 * backed by payments-api" on their profile and a recruiter who reads the same
 * bar on the same candidate are looking at one number with one derivation
 * (`candidate_skills.evidence_weight`). Two renderings would eventually be
 * two numbers, and the first time a candidate and a recruiter compared notes,
 * the product would be the thing that was wrong.
 */
function EvidenceBar({ reason }: { reason: EvidenceSkillReason }) {
  const percent = Math.round((reason.evidence_weight ?? 0) * 100);
  const source = reason.evidence_sources[0];

  return (
    <li className="space-y-1">
      <div className="flex items-baseline justify-between gap-3">
        <span className="truncate text-[13px] font-medium text-ink">{reason.skill_name}</span>
        <span className="tabular shrink-0 text-xs text-slate-500">{percent}%</span>
      </div>
      <div className="h-1.5 w-full rounded-full bg-slate-100">
        <div
          className="h-1.5 rounded-full bg-verified"
          style={{ width: `${Math.max(0, Math.min(100, percent))}%` }}
        />
      </div>
      {source ? (
        <p className="truncate text-[11px] text-slate-400">
          {source.repo_url ? (
            <a
              href={source.repo_url}
              target="_blank"
              rel="noreferrer noopener"
              className="inline-flex items-center gap-1 hover:text-ink hover:underline"
            >
              {source.title ?? source.repo_url}
              <ExternalLink size={9} aria-hidden="true" />
            </a>
          ) : (
            (source.title ?? source.type)
          )}
          {source.verification_score !== null && source.verification_score !== undefined
            ? ` · verification ${Math.round(source.verification_score)}`
            : null}
        </p>
      ) : (
        // The weight exists, the trail does not. Saying so beats a bar that
        // implies a source it cannot name.
        <p className="text-[11px] text-slate-400">No linked repository</p>
      )}
    </li>
  );
}

/* ==================================================================
   SECTION 3 — SUPPORTING SIGNALS
   ================================================================== */

/**
 * Coding-platform ratings and certificates.
 *
 * **No bars and no percentages here, deliberately.** A Codeforces rating and
 * a verified commit history are not the same kind of claim: one is a number
 * another site computed about a handle we checked was reachable, the other is
 * an artefact this system read. Rendering them in the same bar would make
 * them look equally checked, and the whole product rests on a recruiter being
 * able to see which is which at a glance. Smaller type, a divider, and an
 * explicit label do that work.
 */
function SupportingSignal({ label, detail, status }: { label: string; detail: string; status: string }) {
  return (
    <li className="flex items-baseline justify-between gap-3 py-1.5">
      <span className="min-w-0 truncate text-xs text-slate-600">
        {label} <span className="text-slate-400">· {detail}</span>
      </span>
      <span
        className={cn(
          "shrink-0 text-[10px] uppercase tracking-wide",
          status === "verified" ? "text-verified" : status === "flagged" ? "text-flagged" : "text-slate-400",
        )}
      >
        {status}
      </span>
    </li>
  );
}

/* ==================================================================
   SECTION 5 — RISK FLAGS
   ================================================================== */

interface RiskFlag {
  label: string;
  detail: string;
}

/**
 * Anything the verification pipeline marked `FLAGGED`, phrased in the words
 * the pipeline itself used.
 *
 * `FLAGGED` is not `REJECTED` (`domains/student/models.py::VerificationStatus`):
 * it means the claim is still visible but could not be *strongly* confirmed —
 * a fork with thin divergence, a certificate whose issuer domain did not
 * match, a coding handle checked only for reachability. Surfacing it verbatim
 * rather than as a severity score is the point; a recruiter can weigh "this
 * is a fork" themselves, and cannot weigh "risk: 0.4".
 */
function collectRiskFlags(record: EvidenceRecord): RiskFlag[] {
  const flags: RiskFlag[] = [];
  const reasonOf = (payload: Record<string, unknown> | null): string | null => {
    const reason = payload?.reason;
    return typeof reason === "string" && reason.trim() ? reason : null;
  };

  for (const project of record.projects) {
    if (project.verification_status !== "flagged") continue;
    flags.push({
      label: project.title,
      detail: reasonOf(project.verification_payload) ?? "Flagged during repository verification.",
    });
  }
  for (const account of record.coding_platform_accounts) {
    if (account.verification_status !== "flagged") continue;
    flags.push({
      label: `${account.platform} — ${account.handle}`,
      detail: reasonOf(account.verification_payload) ?? "Handle could not be strongly confirmed.",
    });
  }
  for (const certificate of record.certificates) {
    if (certificate.verification_status !== "flagged") continue;
    flags.push({
      label: certificate.title,
      detail: `Issued by ${certificate.issuer} — could not be independently confirmed.`,
    });
  }
  if (record.github_account?.verification_status === "flagged") {
    flags.push({
      label: `GitHub — ${record.github_account.username}`,
      detail: "Account ownership could not be strongly confirmed.",
    });
  }
  return flags;
}

/* ==================================================================
   SECTION 4 — INTERVIEW HIGHLIGHTS
   ================================================================== */

const MAX_HIGHLIGHTS = 4;
const EXCERPT_CHARS = 180;

interface Highlight {
  interviewId: string;
  prompt: string;
  excerpt: string;
  score: number;
}

/**
 * The strongest few answers across every completed interview.
 *
 * Ranked by `weighted_score` and truncated to a sentence, because this is a
 * teaser for the full transcript, not a substitute for it — the link below
 * the list is the real artefact. Truncation cuts on the last sentence
 * boundary inside the budget so an excerpt never ends mid-clause and
 * accidentally reverses what the candidate said.
 */
function collectHighlights(record: EvidenceRecord): Highlight[] {
  const all: Highlight[] = [];
  for (const interview of record.interviews) {
    for (const question of interview.evidence_report?.questions ?? []) {
      const transcript = (question.transcript ?? "").trim();
      if (!transcript) continue;
      all.push({
        interviewId: interview.interview_id,
        prompt: question.prompt,
        excerpt: excerpt(transcript),
        score: question.weighted_score,
      });
    }
  }
  return all.sort((a, b) => b.score - a.score).slice(0, MAX_HIGHLIGHTS);
}

function excerpt(text: string): string {
  if (text.length <= EXCERPT_CHARS) return text;
  const window = text.slice(0, EXCERPT_CHARS);
  const lastStop = Math.max(window.lastIndexOf(". "), window.lastIndexOf("! "), window.lastIndexOf("? "));
  return lastStop > EXCERPT_CHARS * 0.5 ? window.slice(0, lastStop + 1) : `${window.trimEnd()}…`;
}

/* ==================================================================
   THE DRAWER
   ================================================================== */

export interface EvidenceDrawerCandidate {
  candidateProfileId: string;
  applicationId: string | null;
  headline: string | null;
  score: number | null;
  reasoning: string;
  appliedAt: string | null;
  /** The next forward stage, already validated against `ALLOWED_MOVES` by the
   * board. `null` on a matched candidate (no application to move) and on a
   * terminal one. */
  nextStage: { label: string; onMove: () => void } | null;
  onDismiss: (() => void) | null;
}

export interface EvidenceDrawerProps {
  candidate: EvidenceDrawerCandidate | null;
  /** The board's job. Required here — the drawer's primary section is
   * "how does this candidate score against *this role*", which is exactly the
   * `match` block the evidence endpoint only returns when given a job. */
  jobId: string;
  onClose: () => void;
  isMoving: boolean;
}

function relativeDays(iso: string): string {
  const days = Math.floor((Date.now() - new Date(iso).getTime()) / 86_400_000);
  if (days <= 0) return "today";
  if (days === 1) return "yesterday";
  return `${days} days ago`;
}

/**
 * Screen 4 — the candidate evidence report, as a right-side drawer.
 *
 * A drawer rather than a route because reviewing a candidate is a detour, not
 * a destination: a recruiter working a column of thirty opens one, decides,
 * and returns to precisely the scroll position they left. A full-page
 * navigation loses that position, and losing it thirty times is the
 * difference between a board someone works through and a board someone
 * abandons.
 */
export function EvidenceDrawer({ candidate, jobId, onClose, isMoving }: EvidenceDrawerProps) {
  const [menuOpen, setMenuOpen] = useState(false);
  const [tab, setTab] = useState<DrawerTab>("Evidence");
  const panelRef = useRef<HTMLDivElement>(null);
  const evidence = useCandidateEvidence(candidate?.candidateProfileId ?? "", jobId);

  useEffect(() => {
    if (!candidate) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKeyDown);
    // Focus moves into the panel so a keyboard user is not left behind on the
    // card they just activated.
    panelRef.current?.focus();
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [candidate, onClose]);

  // Both reset when the drawer is pointed at a different candidate: an open
  // menu belongs to the card it was opened from, and landing on the Interview
  // tab for someone you just clicked is disorienting when the reason you
  // clicked was to read their evidence.
  useEffect(() => {
    setMenuOpen(false);
    setTab("Evidence");
  }, [candidate]);

  const record = evidence.data;
  const verifiedSkills = useMemo(() => {
    if (!record?.match) return [];
    return [...record.match.matched_required_skills, ...record.match.matched_desirable_skills]
      .filter((reason) => reason.candidate_has_skill)
      .sort((a, b) => (b.evidence_weight ?? 0) - (a.evidence_weight ?? 0));
  }, [record]);
  const riskFlags = useMemo(() => (record ? collectRiskFlags(record) : []), [record]);
  const highlights = useMemo(() => (record ? collectHighlights(record) : []), [record]);
  const radarAxes = useMemo(() => (record ? buildRadarAxes(record) : []), [record]);

  if (!candidate) return null;

  return (
    <>
      {/* Deliberately not `bg-slate-900/40` like `Modal`: the board behind
          this stays legible on purpose, because half of reviewing a candidate
          is comparing them to the column they are in. */}
      <div className="fixed inset-0 z-40 bg-slate-900/10" onClick={onClose} aria-hidden="true" />

      <aside
        ref={panelRef}
        tabIndex={-1}
        role="dialog"
        aria-modal="true"
        aria-label={`Evidence report — ${candidate.headline ?? "candidate"}`}
        className="fixed inset-y-0 right-0 z-50 flex w-full max-w-[480px] animate-slide-up flex-col border-l border-rule bg-white shadow-raised outline-none"
      >
        {/* ---- header ---- */}
        <header className="shrink-0 border-b border-rule px-5 py-4">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <h2 className="truncate font-display text-lg font-semibold tracking-tight text-ink">
                {candidate.headline ?? "Candidate"}
              </h2>
              <p className="mt-0.5 flex flex-wrap items-center gap-x-1.5 text-xs text-slate-500">
                <MatchScore score={candidate.score} size="sm" />
                {candidate.appliedAt ? <span>· Applied {relativeDays(candidate.appliedAt)}</span> : null}
              </p>
            </div>
            <div className="flex shrink-0 items-center gap-2">
              {record?.profile.is_discoverable ? (
                <span className="inline-flex items-center gap-1 rounded-full border border-verified/30 bg-verified/5 px-2 py-0.5 text-[11px] font-medium text-verified">
                  <BadgeCheck size={11} aria-hidden="true" />
                  Verified
                </span>
              ) : null}
              <button
                type="button"
                onClick={onClose}
                aria-label="Close evidence report"
                className="rounded p-1 text-slate-400 transition hover:bg-slate-100 hover:text-slate-700"
              >
                <X size={17} aria-hidden="true" />
              </button>
            </div>
          </div>
        </header>

        {/* ---- tabs ---- */}
        <div className="shrink-0 border-b border-rule px-5" role="tablist" aria-label="Candidate report sections">
          <div className="flex gap-4">
            {TABS.map((name) => (
              <button
                key={name}
                type="button"
                role="tab"
                aria-selected={tab === name}
                onClick={() => setTab(name)}
                className={cn(
                  "-mb-px border-b-2 py-2.5 text-xs font-medium transition",
                  tab === name
                    ? "border-gt-electric text-ink"
                    : "border-transparent text-slate-400 hover:text-slate-600",
                )}
              >
                {name}
              </button>
            ))}
          </div>
        </div>

        {/* ---- body ---- */}
        <div className="flex-1 overflow-y-auto px-5 py-4">
          {evidence.isPending ? (
            <div className="space-y-3">
              <Skeleton className="h-16 w-full" />
              <Skeleton className="h-40 w-full" />
              <Skeleton className="h-24 w-full" />
            </div>
          ) : evidence.isError || !record ? (
            <ErrorState
              title="Could not load this candidate's evidence"
              description="The report is built from stored verification records. Try again in a moment."
            />
          ) : (
            <div className="space-y-6">
              {tab === "Evidence" ? (
                <>
              {/* 1 — match reasoning */}
              {candidate.reasoning ? (
                <section className="border-l-2 border-gt-electric bg-gt-electric/5 py-2.5 pl-3.5 pr-3">
                  <p className="text-[13px] leading-relaxed text-slate-700">{candidate.reasoning}</p>
                </section>
              ) : null}

              {/* 2 — verified skills, the primary section */}
              <section>
                <h3 className="mb-2.5 text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                  Verified skills
                </h3>
                {verifiedSkills.length === 0 ? (
                  <p className="text-xs text-slate-400">
                    No skill on this job’s requirement list has verified evidence behind it yet.
                  </p>
                ) : (
                  <ul className="space-y-3">
                    {verifiedSkills.map((reason) => (
                      <EvidenceBar key={reason.skill_name} reason={reason} />
                    ))}
                  </ul>
                )}
              </section>

              {/* 2b — coverage against the role, as a shape.

                  Sits under the bars, not above them: the bars are the
                  evidence and this is a summary of it. A recruiter who reads
                  only one should read the one with the repository links. */}
              {radarAxes.length >= 3 ? (
                <section>
                  <h3 className="mb-1 text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                    Coverage of this role
                  </h3>
                  <SkillRadar axes={radarAxes} className="h-52 w-full" />
                </section>
              ) : null}

              {/* 3 — supporting signals */}
              {record.coding_platform_accounts.length > 0 || record.certificates.length > 0 ? (
                <section className="border-t border-rule pt-4">
                  <h3 className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                    Supporting signals
                  </h3>
                  <p className="mb-1.5 text-[11px] text-slate-400">Not independently verified.</p>
                  <ul className="divide-y divide-rule/60">
                    {record.coding_platform_accounts.map((account) => (
                      <SupportingSignal
                        key={`${account.platform}-${account.handle}`}
                        label={account.platform}
                        detail={account.handle}
                        status={account.verification_status}
                      />
                    ))}
                    {record.certificates.map((certificate) => (
                      <SupportingSignal
                        key={certificate.title}
                        label={certificate.title}
                        detail={certificate.issuer}
                        status={certificate.verification_status}
                      />
                    ))}
                  </ul>
                </section>
              ) : null}

              {/* 4 — the strongest few answers, as a teaser. The Interview
                  tab carries the full transcript and the rubric breakdown;
                  this stays here because "did they explain their own code"
                  is part of deciding whether to keep reading at all. */}
              {highlights.length > 0 ? (
                <section className="border-t border-rule pt-4">
                  <h3 className="mb-2.5 text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                    Interview highlights
                  </h3>
                  <ul className="space-y-2">
                    {highlights.map((highlight, index) => (
                      <li key={`${highlight.interviewId}-${index}`} className="rounded-lg bg-panel p-3">
                        <p className="text-[11px] font-medium text-slate-600">{highlight.prompt}</p>
                        <p className="mt-1.5 border-l-2 border-rule pl-2.5 text-xs italic leading-relaxed text-slate-500">
                          “{highlight.excerpt}”
                        </p>
                      </li>
                    ))}
                  </ul>
                  <button
                    type="button"
                    onClick={() => setTab("Interview")}
                    className="mt-2 inline-flex items-center gap-1 text-[11px] font-medium text-gt-electric hover:underline"
                  >
                    Full transcript and per-criterion scores
                    <ArrowRight size={11} aria-hidden="true" />
                  </button>
                </section>
              ) : null}

              {/* 5 — risk flags, only when there are any */}
              {riskFlags.length > 0 ? (
                <section className="rounded-lg bg-[#FEF3C7] px-3.5 py-3">
                  <h3 className="mb-1.5 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider text-amber-800">
                    <AlertTriangle size={12} aria-hidden="true" />
                    Risk flags
                  </h3>
                  <ul className="space-y-2">
                    {riskFlags.map((flag) => (
                      <li key={flag.label} className="text-xs leading-relaxed text-amber-800">
                        <span className="font-medium">{flag.label}</span> — {flag.detail}
                      </li>
                    ))}
                  </ul>
                </section>
              ) : null}
                </>
              ) : tab === "Interview" ? (
                <InterviewTab record={record} />
              ) : (
                <ActivityTab record={record} appliedAt={candidate.appliedAt} />
              )}
            </div>
          )}
        </div>

        {/* ---- sticky actions ---- */}
        <footer className="relative flex shrink-0 items-center gap-2 border-t border-rule bg-white px-5 py-3.5">
          {candidate.applicationId ? (
            <Link
              to={`/recruiter/applications/${candidate.applicationId}`}
              className="inline-flex items-center gap-1.5 rounded border border-ink px-3.5 py-2 text-xs font-bold text-ink transition hover:bg-ink/5"
            >
              <MessageSquare size={13} aria-hidden="true" />
              Message
            </Link>
          ) : (
            // Messaging is scoped to an existing pipeline relationship — the
            // `conversations.application_id` FK *is* that rule, so there is
            // nothing to open for a candidate who has not applied.
            <span
              className="inline-flex cursor-not-allowed items-center gap-1.5 rounded border border-rule px-3.5 py-2 text-xs font-bold text-slate-300"
              title="Messaging opens once the candidate applies"
            >
              <MessageSquare size={13} aria-hidden="true" />
              Message
            </span>
          )}

          {candidate.nextStage ? (
            <Button
              type="button"
              size="sm"
              isLoading={isMoving}
              onClick={candidate.nextStage.onMove}
              className="bg-gt-electric hover:bg-gt-electric/90"
            >
              {candidate.nextStage.label}
              <ArrowRight size={13} aria-hidden="true" />
            </Button>
          ) : null}

          <div className="ml-auto">
            <button
              type="button"
              onClick={() => setMenuOpen((open) => !open)}
              aria-label="More actions"
              aria-expanded={menuOpen}
              className="rounded p-1.5 text-slate-400 transition hover:bg-slate-100 hover:text-slate-700"
            >
              <MoreHorizontal size={17} aria-hidden="true" />
            </button>
            {menuOpen ? (
              <div className="absolute bottom-14 right-5 w-48 overflow-hidden rounded-lg border border-rule bg-white py-1 shadow-raised">
                <Link
                  to={`/recruiter/candidates/${candidate.candidateProfileId}/evidence`}
                  className="block px-3 py-2 text-xs text-slate-600 transition hover:bg-slate-50"
                >
                  View full report
                </Link>
                {candidate.onDismiss ? (
                  <button
                    type="button"
                    onClick={() => {
                      setMenuOpen(false);
                      candidate.onDismiss?.();
                    }}
                    className="block w-full px-3 py-2 text-left text-xs text-red-600 transition hover:bg-red-50"
                  >
                    Dismiss candidate
                  </button>
                ) : null}
              </div>
            ) : null}
          </div>
        </footer>
      </aside>
    </>
  );
}
