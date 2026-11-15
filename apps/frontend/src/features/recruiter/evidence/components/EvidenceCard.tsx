import { Award, Briefcase, Code2, ExternalLink, GitBranch, Target } from "lucide-react";
import type { ReactNode } from "react";

import { Badge, Card, ErrorState, Skeleton } from "@/components";
import { SkillRadar } from "@/components/charts/SkillRadar";
import { ProgressRing } from "@/design/primitives";
import { Surface } from "@/design/Surface";
import { VerificationBadge } from "@/features/student/components/SectionBadges";

import { useCandidateEvidence } from "../hooks/useEvidence";
import { InterviewTab } from "./evidenceTabs";
import { buildRadarAxes } from "./radarAxes";
import { initialsFrom } from "../../pipeline/lib/cardIdentity";
import type { EvidenceSkillReason } from "../api/evidenceApi";

/** Section heading: overline label, optional icon, optional count. */
function SectionTitle({ icon, title, count }: { icon: ReactNode; title: string; count?: number }) {
  return (
    <h2 className="mb-3 flex items-center gap-2 font-display text-lg font-semibold text-[var(--ink)]">
      {icon}
      {title}
      {count !== undefined ? (
        <span className="tabular rounded-full bg-[var(--panel-raised)] px-2 py-0.5 text-[11px] font-semibold text-[var(--slate)]">
          {count}
        </span>
      ) : null}
    </h2>
  );
}

function EmptyNote({ children }: { children: ReactNode }) {
  return (
    <p className="rounded-[var(--r-md)] border border-dashed border-[var(--rule)] px-4 py-6 text-center text-sm text-[var(--muted)]">
      {children}
    </p>
  );
}

/**
 * One skill's evidence weight, as a bar — identical in construction to the
 * drawer's `EvidenceBar` (6px track, `--verified` fill, right-aligned
 * percentage), so the card and the drawer can never disagree about a skill.
 * The weight is `candidate_skills.evidence_weight`: how much stored,
 * verified evidence backs this skill, not a proficiency guess.
 */
function SkillEvidenceBar({ reason }: { reason: EvidenceSkillReason }) {
  const percent = Math.round((reason.evidence_weight ?? 0) * 100);
  const source = reason.evidence_sources[0];

  return (
    <li className="space-y-1">
      <div className="flex items-baseline justify-between gap-3">
        <span className="truncate text-[13px] font-medium text-[var(--ink)]">{reason.skill_name}</span>
        <span className="tabular shrink-0 text-xs text-[var(--slate)]">{percent}%</span>
      </div>
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-[var(--panel-raised)]">
        <div
          className="h-1.5 rounded-full bg-[var(--verified)]"
          style={{ width: `${Math.max(0, Math.min(100, percent))}%` }}
        />
      </div>
      {source ? (
        <p className="truncate text-[11px] text-[var(--muted)]">
          {source.repo_url ? (
            <a
              href={source.repo_url}
              target="_blank"
              rel="noreferrer noopener"
              className="inline-flex items-center gap-1 hover:text-[var(--ink)] hover:underline"
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
        <p className="text-[11px] text-[var(--muted)]">No linked repository</p>
      )}
    </li>
  );
}

/** The recruiter's candidate evidence card — contribution analysis,
 * interview transcript with per-criterion scores, coding-platform stats,
 * and certificates, all read from one endpoint
 * (`GET /recruiter/candidates/{id}/evidence`) that is the exact same
 * builder used for `Application.evidence_snapshot`, so nothing here is
 * narrated or recomputed. */
export function EvidenceCard({ candidateProfileId }: { candidateProfileId: string }) {
  const evidence = useCandidateEvidence(candidateProfileId);

  if (evidence.isPending) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-32 w-full" />
        <Skeleton className="h-48 w-full" />
        <Skeleton className="h-32 w-full" />
      </div>
    );
  }

  if (evidence.isError || !evidence.data) {
    return <ErrorState title="Could not load candidate evidence" description="Something went wrong." />;
  }

  const record = evidence.data;
  const radarAxes = buildRadarAxes(record);

  // Counts of stored records only — "why this candidate qualifies" at a
  // glance, with no number the endpoint did not return. A verified repo is
  // one whose `verification_status` is `verified`; an interview is one the
  // candidate completed, whether or not it produced a report.
  const verifiedRepos = record.projects.filter((p) => p.verification_status === "verified").length;
  const verifiedCerts = record.certificates.filter((c) => c.verification_status === "verified").length;
  const verifiedAccounts =
    (record.github_account?.verification_status === "verified" ? 1 : 0) +
    record.coding_platform_accounts.filter((a) => a.verification_status === "verified").length;
  const completedInterviews = record.interviews.length;

  const verifiedSkills = record.match
    ? [...record.match.matched_required_skills, ...record.match.matched_desirable_skills]
        .filter((reason) => reason.candidate_has_skill)
        .sort((a, b) => (b.evidence_weight ?? 0) - (a.evidence_weight ?? 0))
    : [];

  const profileMeta = [
    record.profile.college,
    record.profile.degree,
    record.profile.branch,
    record.profile.graduation_year ? `Class of ${record.profile.graduation_year}` : null,
    record.profile.location,
  ]
    .filter(Boolean)
    .join(" · ");

  return (
    <div className="space-y-6">
      {/* ---- identity + why they qualify ---- */}
      <Card elevation="raised">
        <div className="flex flex-wrap items-start gap-4">
          <span
            aria-hidden="true"
            className="flex h-14 w-14 shrink-0 items-center justify-center rounded-full bg-gt-electric/10 text-base font-semibold text-gt-electric"
          >
            {initialsFrom(record.profile.headline)}
          </span>
          <div className="min-w-0 flex-1">
            <p className="font-display text-lg font-semibold tracking-tight text-[var(--ink)]">
              {record.profile.headline ?? "Candidate"}
            </p>
            {profileMeta ? <p className="mt-0.5 text-sm text-[var(--slate)]">{profileMeta}</p> : null}
            {record.profile.target_role ? (
              <p className="mt-1.5">
                <Badge variant="accent">Targeting {record.profile.target_role}</Badge>
              </p>
            ) : null}
          </div>
          <div className="flex shrink-0 flex-col items-center">
            <ProgressRing value={record.profile.profile_strength} size={88} strokeWidth={7}>
              <span className="tabular text-lg font-semibold text-[var(--ink)]">
                {Math.round(record.profile.profile_strength)}
              </span>
            </ProgressRing>
            <p className="mt-1 text-[11px] text-[var(--muted)]">profile strength</p>
          </div>
        </div>

        {record.match ? (
          <dl className="mt-4 grid grid-cols-3 gap-3 border-t border-[var(--rule-soft)] pt-4">
            <div>
              <dt className="text-[11px] font-medium uppercase tracking-wide text-[var(--muted)]">Match</dt>
              <dd className="tabular mt-0.5 text-xl font-semibold text-gt-electric">
                {record.match.match_score.toFixed(0)}%
              </dd>
            </div>
            <div>
              <dt className="text-[11px] font-medium uppercase tracking-wide text-[var(--muted)]">Semantic</dt>
              <dd className="tabular mt-0.5 text-xl font-semibold text-[var(--ink)]">
                {(record.match.semantic_score * 100).toFixed(0)}%
              </dd>
            </div>
            <div>
              <dt className="text-[11px] font-medium uppercase tracking-wide text-[var(--muted)]">Evidence</dt>
              <dd className="tabular mt-0.5 text-xl font-semibold text-[var(--ink)]">
                {(record.match.evidence_score * 100).toFixed(0)}%
              </dd>
            </div>
          </dl>
        ) : null}

        {/* What backs the candidate, counted from the record — not a score
            invented for this card. */}
        <dl className="mt-4 flex flex-wrap gap-x-6 gap-y-2 border-t border-[var(--rule-soft)] pt-4 text-sm">
          <div className="flex items-baseline gap-1.5">
            <dt className="text-[var(--slate)]">Verified repositories</dt>
            <dd className="tabular font-semibold text-[var(--ink)]">
              {verifiedRepos} of {record.projects.length}
            </dd>
          </div>
          <div className="flex items-baseline gap-1.5">
            <dt className="text-[var(--slate)]">Verified accounts</dt>
            <dd className="tabular font-semibold text-[var(--ink)]">
              {verifiedAccounts} of {record.coding_platform_accounts.length + (record.github_account ? 1 : 0)}
            </dd>
          </div>
          <div className="flex items-baseline gap-1.5">
            <dt className="text-[var(--slate)]">Verified certificates</dt>
            <dd className="tabular font-semibold text-[var(--ink)]">
              {verifiedCerts} of {record.certificates.length}
            </dd>
          </div>
          <div className="flex items-baseline gap-1.5">
            <dt className="text-[var(--slate)]">Interviews completed</dt>
            <dd className="tabular font-semibold text-[var(--ink)]">{completedInterviews}</dd>
          </div>
        </dl>
      </Card>

      {/* ---- verified skills for this role ---- */}
      {record.match ? (
        <section>
          <SectionTitle
            icon={<Target size={16} aria-hidden="true" />}
            title="Verified skills for this role"
            count={verifiedSkills.length}
          />
          {verifiedSkills.length === 0 ? (
            <EmptyNote>No skill on this job’s requirement list has verified evidence behind it yet.</EmptyNote>
          ) : (
            <Surface className="p-5">
              <ul className="space-y-3">
                {verifiedSkills.map((reason) => (
                  <SkillEvidenceBar key={reason.skill_name} reason={reason} />
                ))}
              </ul>
            </Surface>
          )}
          {radarAxes.length >= 3 ? (
            <Surface className="mt-3 p-5">
              <h3 className="mb-1 text-[11px] font-semibold uppercase tracking-wider text-[var(--slate)]">
                Coverage of this role
              </h3>
              <SkillRadar axes={radarAxes} className="h-56 w-full" />
            </Surface>
          ) : null}
        </section>
      ) : (
        <EmptyNote>
          No job context for this view, so there is no match to break down — the evidence below is
          the candidate’s own record.
        </EmptyNote>
      )}

      {record.skills.length > 0 ? (
        <section>
          <SectionTitle icon={<Code2 size={16} aria-hidden="true" />} title="Skills" count={record.skills.length} />
          <div className="flex flex-wrap gap-1.5">
            {record.skills.map((skill) => (
              <Badge key={skill.name} variant="neutral" title={skill.proficiency ? `Proficiency: ${skill.proficiency}` : undefined}>
                {skill.name}
                {skill.proficiency ? <span className="text-[var(--muted)]">· {skill.proficiency}</span> : null}
              </Badge>
            ))}
          </div>
        </section>
      ) : null}

      <section>
        <SectionTitle
          icon={<GitBranch size={16} aria-hidden="true" />}
          title="Repositories & contribution analysis"
          count={record.projects.length}
        />
        {record.projects.length === 0 ? (
          <EmptyNote>No repositories submitted.</EmptyNote>
        ) : (
          <div className="space-y-2">
            {record.projects.map((project) => {
              const contributionShare = project.verification_payload?.contribution_share as number | undefined;
              return (
                <Surface key={project.title} className="p-4">
                  <div className="flex items-center justify-between gap-3">
                    {project.repo_url ? (
                      <a
                        href={project.repo_url}
                        target="_blank"
                        rel="noreferrer noopener"
                        className="inline-flex min-w-0 items-center gap-1.5 font-medium text-[var(--ink)] hover:text-gt-electric hover:underline"
                      >
                        <span className="truncate">{project.title}</span>
                        <ExternalLink size={12} className="shrink-0" aria-hidden="true" />
                      </a>
                    ) : (
                      <p className="font-medium text-[var(--ink)]">{project.title}</p>
                    )}
                    <VerificationBadge status={project.verification_status} />
                  </div>
                  <div className="mt-1.5 flex flex-wrap items-center gap-3 text-xs text-[var(--slate)]">
                    {contributionShare !== undefined ? (
                      <span className="tabular">{Math.round(contributionShare * 100)}% contribution</span>
                    ) : null}
                    {project.verification_score !== null ? (
                      <span className="tabular">Score {project.verification_score.toFixed(0)}</span>
                    ) : null}
                    {project.technologies.slice(0, 5).map((tech) => (
                      <Badge key={tech} variant="neutral">
                        {tech}
                      </Badge>
                    ))}
                  </div>
                </Surface>
              );
            })}
          </div>
        )}
      </section>

      {record.interviews.length > 0 ? (
        <section>
          <SectionTitle
            icon={<Code2 size={16} aria-hidden="true" />}
            title="Code-grounded interviews"
            count={record.interviews.length}
          />
          {/* The same component the drawer's Interview tab renders, rather
              than the candidate's own report view. The two used to share
              `EvidenceReportView`, which worked only while the report was one
              self-contained blob; now that the scores and the conversation
              are rows in their own right, the recruiter-side reader is the one
              that knows how to assemble them — and one reader means the card
              and the drawer cannot drift. */}
          <InterviewTab record={record} />
        </section>
      ) : null}

      <section>
        <SectionTitle
          icon={<Code2 size={16} aria-hidden="true" />}
          title="Coding platforms"
          count={record.coding_platform_accounts.length + (record.github_account ? 1 : 0)}
        />
        {record.github_account === null && record.coding_platform_accounts.length === 0 ? (
          <EmptyNote>No coding accounts connected.</EmptyNote>
        ) : (
          <div className="space-y-2">
            {record.github_account ? (
              <Surface className="flex items-center justify-between gap-3 p-3.5">
                <span className="text-sm text-[var(--ink)]">
                  GitHub — <span className="machine">{record.github_account.username}</span>
                </span>
                <VerificationBadge status={record.github_account.verification_status} />
              </Surface>
            ) : null}
            {record.coding_platform_accounts.map((account) => (
              <Surface key={`${account.platform}-${account.handle}`} className="flex items-center justify-between gap-3 p-3.5">
                <span className="text-sm capitalize text-[var(--ink)]">
                  {account.platform} — <span className="machine">{account.handle}</span>
                  {account.verification_score !== null ? (
                    <span className="tabular ml-2 text-xs text-[var(--slate)]">
                      score {account.verification_score.toFixed(0)}
                    </span>
                  ) : null}
                </span>
                <VerificationBadge status={account.verification_status} />
              </Surface>
            ))}
          </div>
        )}
      </section>

      <section>
        <SectionTitle
          icon={<Award size={16} aria-hidden="true" />}
          title="Certificates"
          count={record.certificates.length}
        />
        {record.certificates.length === 0 ? (
          <EmptyNote>No certificates submitted.</EmptyNote>
        ) : (
          <div className="space-y-2">
            {record.certificates.map((cert) => (
              <Surface key={cert.title} className="flex items-center justify-between gap-3 p-3.5">
                <span className="text-sm text-[var(--ink)]">
                  {cert.title} <span className="text-[var(--muted)]">· {cert.issuer}</span>
                  {cert.verification_score !== null ? (
                    <span className="tabular ml-2 text-xs text-[var(--slate)]">
                      score {cert.verification_score.toFixed(0)}
                    </span>
                  ) : null}
                </span>
                <VerificationBadge status={cert.verification_status} />
              </Surface>
            ))}
          </div>
        )}
      </section>

      {record.experiences.length > 0 ? (
        <section>
          <SectionTitle
            icon={<Briefcase size={16} aria-hidden="true" />}
            title="Experience"
            count={record.experiences.length}
          />
          <div className="space-y-2">
            {record.experiences.map((exp) => (
              <Surface key={`${exp.company_name}-${exp.title}`} className="flex items-center justify-between gap-3 p-3.5">
                <span className="text-sm text-[var(--ink)]">
                  {exp.title} <span className="text-[var(--muted)]">· {exp.company_name}</span>
                  {exp.employment_type ? (
                    <span className="ml-2 text-xs capitalize text-[var(--muted)]">
                      {exp.employment_type.replace(/_/g, " ")}
                    </span>
                  ) : null}
                </span>
                <VerificationBadge status={exp.verification_status} />
              </Surface>
            ))}
          </div>
        </section>
      ) : null}
    </div>
  );
}
