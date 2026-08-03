import { Award, Briefcase, Code2, GitBranch } from "lucide-react";

import { Badge, ErrorState, Skeleton } from "@/components";
import { EvidenceReportView } from "@/features/student/interview/components/EvidenceReportView";
import { VerificationBadge } from "@/features/student/components/SectionBadges";

import { useCandidateEvidence } from "../hooks/useEvidence";

/** The recruiter's candidate evidence card — contribution analysis,
 * interview transcript with per-criterion scores, coding-platform stats,
 * and certificates, all read from one endpoint
 * (`GET /recruiter/candidates/{id}/evidence`) that is the exact same
 * builder used for `Application.evidence_snapshot`, so nothing here is
 * narrated or recomputed. */
export function EvidenceCard({ candidateProfileId }: { candidateProfileId: string }) {
  const evidence = useCandidateEvidence(candidateProfileId);

  if (evidence.isPending) {
    return <Skeleton className="h-96 w-full" />;
  }

  if (evidence.isError || !evidence.data) {
    return <ErrorState title="Could not load candidate evidence" description="Something went wrong." />;
  }

  const record = evidence.data;

  return (
    <div className="space-y-6">
      <div className="rounded-2xl border border-rule bg-white p-5">
        <div className="mb-3 flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="font-medium text-ink">{record.profile.headline ?? "Candidate"}</p>
            <p className="text-xs text-slate-500">
              {[record.profile.college, record.profile.degree, record.profile.location].filter(Boolean).join(" · ")}
            </p>
          </div>
          <div className="text-right">
            <p className="text-2xl font-semibold tabular-nums text-ink">{record.profile.profile_strength}</p>
            <p className="text-xs text-slate-400">profile strength</p>
          </div>
        </div>
        {record.match ? (
          <div className="flex flex-wrap gap-3 text-xs text-slate-500">
            <span>Match {record.match.match_score.toFixed(0)}</span>
            <span>Semantic {(record.match.semantic_score * 100).toFixed(0)}%</span>
            <span>Evidence {(record.match.evidence_score * 100).toFixed(0)}%</span>
          </div>
        ) : null}
        {record.skills.length > 0 ? (
          <div className="mt-3 flex flex-wrap gap-1.5">
            {record.skills.map((skill) => (
              <Badge key={skill.name} variant="neutral">
                {skill.name}
              </Badge>
            ))}
          </div>
        ) : null}
      </div>

      <section>
        <h2 className="mb-3 flex items-center gap-2 font-display text-lg font-semibold text-ink">
          <GitBranch size={16} aria-hidden="true" /> Repositories &amp; contribution analysis
        </h2>
        {record.projects.length === 0 ? (
          <p className="text-sm text-slate-400">No repositories submitted.</p>
        ) : (
          <div className="space-y-2">
            {record.projects.map((project) => {
              const contributionShare = project.verification_payload?.contribution_share as number | undefined;
              return (
                <div key={project.title} className="rounded-2xl border border-rule bg-white p-4">
                  <div className="flex items-center justify-between gap-3">
                    <p className="font-medium text-ink">{project.title}</p>
                    <VerificationBadge status={project.verification_status} />
                  </div>
                  <div className="mt-1.5 flex flex-wrap items-center gap-3 text-xs text-slate-500">
                    {contributionShare !== undefined ? <span>{Math.round(contributionShare * 100)}% contribution</span> : null}
                    {project.verification_score !== null ? <span>Score {project.verification_score.toFixed(0)}</span> : null}
                    {project.technologies.slice(0, 5).map((tech) => (
                      <Badge key={tech} variant="neutral">
                        {tech}
                      </Badge>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </section>

      {record.interviews.length > 0 ? (
        <section>
          <h2 className="mb-3 font-display text-lg font-semibold text-ink">Code-grounded interviews</h2>
          <div className="space-y-6">
            {record.interviews.map((interview) =>
              interview.evidence_report ? (
                <div key={interview.interview_id}>
                  <p className="mb-2 text-sm font-medium text-slate-600">{interview.project_title}</p>
                  <EvidenceReportView report={interview.evidence_report} />
                </div>
              ) : null,
            )}
          </div>
        </section>
      ) : null}

      <section>
        <h2 className="mb-3 flex items-center gap-2 font-display text-lg font-semibold text-ink">
          <Code2 size={16} aria-hidden="true" /> Coding platforms
        </h2>
        {record.github_account === null && record.coding_platform_accounts.length === 0 ? (
          <p className="text-sm text-slate-400">No coding accounts connected.</p>
        ) : (
          <div className="space-y-2">
            {record.github_account ? (
              <div className="flex items-center justify-between rounded-2xl border border-rule bg-white p-3.5">
                <span className="text-sm text-ink">GitHub — {record.github_account.username}</span>
                <VerificationBadge status={record.github_account.verification_status} />
              </div>
            ) : null}
            {record.coding_platform_accounts.map((account) => (
              <div key={`${account.platform}-${account.handle}`} className="flex items-center justify-between rounded-2xl border border-rule bg-white p-3.5">
                <span className="text-sm capitalize text-ink">
                  {account.platform} — {account.handle}
                </span>
                <VerificationBadge status={account.verification_status} />
              </div>
            ))}
          </div>
        )}
      </section>

      <section>
        <h2 className="mb-3 flex items-center gap-2 font-display text-lg font-semibold text-ink">
          <Award size={16} aria-hidden="true" /> Certificates
        </h2>
        {record.certificates.length === 0 ? (
          <p className="text-sm text-slate-400">No certificates submitted.</p>
        ) : (
          <div className="space-y-2">
            {record.certificates.map((cert) => (
              <div key={cert.title} className="flex items-center justify-between rounded-2xl border border-rule bg-white p-3.5">
                <span className="text-sm text-ink">
                  {cert.title} <span className="text-slate-400">· {cert.issuer}</span>
                </span>
                <VerificationBadge status={cert.verification_status} />
              </div>
            ))}
          </div>
        )}
      </section>

      {record.experiences.length > 0 ? (
        <section>
          <h2 className="mb-3 flex items-center gap-2 font-display text-lg font-semibold text-ink">
            <Briefcase size={16} aria-hidden="true" /> Experience
          </h2>
          <div className="space-y-2">
            {record.experiences.map((exp) => (
              <div key={`${exp.company_name}-${exp.title}`} className="flex items-center justify-between rounded-2xl border border-rule bg-white p-3.5">
                <span className="text-sm text-ink">
                  {exp.title} <span className="text-slate-400">· {exp.company_name}</span>
                </span>
                <VerificationBadge status={exp.verification_status} />
              </div>
            ))}
          </div>
        </section>
      ) : null}
    </div>
  );
}
