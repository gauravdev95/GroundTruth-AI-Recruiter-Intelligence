import { Award, Briefcase, Code2, Eye } from "lucide-react";
import { Link } from "react-router-dom";

import { Badge, ErrorState, Skeleton } from "@/components";
import { DeadLetterBanner } from "@/features/jobs";

import { useStudentAnalytics } from "../analytics/hooks/useStudentAnalytics";
import { JobFeedPreview } from "../matches/components/JobFeedPreview";
import { ProfileStrengthMeter } from "../components/ProfileStrengthMeter";
import { RepoEvidenceCard } from "../components/RepoEvidenceCard";
import { VerificationBadge } from "../components/SectionBadges";
import { useCertificatesSection, useProfileCompleteness, useProjectsSection, useTechnicalSection } from "../hooks/useProfileSection";

function StatTile({ icon: Icon, label, value }: { icon: typeof Briefcase; label: string; value: number | string }) {
  return (
    <div className="flex items-center gap-3 rounded-2xl border border-rule bg-white p-4">
      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-ink/5 text-ink">
        <Icon size={16} aria-hidden="true" />
      </div>
      <div>
        <p className="text-lg font-semibold tabular-nums text-ink">{value}</p>
        <p className="text-xs text-slate-500">{label}</p>
      </div>
    </div>
  );
}

/** The real candidate dashboard home: profile strength breakdown, per-claim
 * verification status, repo evidence cards, coding-platform stats,
 * certificate status, and match count — every number read straight from the
 * server, nothing recomputed client-side (same principle as the job feed). */
export function DashboardHome() {
  const completeness = useProfileCompleteness();
  const technical = useTechnicalSection();
  const projects = useProjectsSection();
  const certificates = useCertificatesSection();
  const analytics = useStudentAnalytics();

  if (completeness.isPending || technical.isPending || projects.isPending || certificates.isPending) {
    return (
      <div className="grid gap-4 md:grid-cols-2">
        <Skeleton className="h-64 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  if (completeness.isError || !completeness.data) {
    return <ErrorState title="Could not load your dashboard" description="Something went wrong." />;
  }

  const codingProfiles = technical.data?.data.coding_profiles ?? [];
  const githubAccount = technical.data?.data.github_account ?? null;
  const projectList = projects.data?.data.projects ?? [];
  const certificateList = certificates.data?.data.certificates ?? [];

  return (
    <div className="space-y-6">
      <header>
        <h1 className="font-display text-2xl font-semibold text-ink">Your dashboard</h1>
        <p className="mt-1 text-sm text-slate-500">
          {completeness.data.is_discoverable
            ? "Your profile is discoverable to recruiters."
            : completeness.data.meets_section_requirements
              ? "Both required sections are done — we're indexing your profile now."
              : "Complete the required sections to become discoverable to recruiters."}
        </p>
      </header>

      <DeadLetterBanner />

      <div className="grid gap-4 sm:grid-cols-3">
        <StatTile icon={Briefcase} label="Job matches" value={analytics.data?.match_count ?? 0} />
        <StatTile icon={Eye} label="Profile views by recruiters" value={analytics.data?.profile_views ?? 0} />
        <StatTile icon={Award} label="Applications sent" value={Object.values(analytics.data?.application_outcomes ?? {}).reduce((a, b) => a + b, 0)} />
      </div>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,320px)_1fr]">
        <ProfileStrengthMeter completeness={completeness.data} />

        <div className="space-y-6">
          {/* The ranked feed lives here as well as on its own page: the flow
              names it as dashboard content, and a student who lands here
              should see what they matched to without a second navigation. */}
          <section>
            <h2 className="mb-3 flex items-center gap-2 font-display text-lg font-semibold text-ink">
              <Briefcase size={18} aria-hidden="true" /> Your job matches
            </h2>
            <JobFeedPreview />
          </section>

          <section>
            <h2 className="mb-3 font-display text-lg font-semibold text-ink">Repositories</h2>
            {projectList.length === 0 ? (
              <p className="rounded-2xl border border-dashed border-rule p-6 text-center text-sm text-slate-500">
                No repositories added yet.{" "}
                <Link to="/student/profile" className="font-medium text-ink hover:underline">
                  Add one in your profile
                </Link>
                .
              </p>
            ) : (
              <div className="grid gap-3 sm:grid-cols-2">
                {projectList.map((project) => (
                  <RepoEvidenceCard key={project.id} project={project} />
                ))}
              </div>
            )}
          </section>

          <section>
            <h2 className="mb-3 flex items-center gap-2 font-display text-lg font-semibold text-ink">
              <Code2 size={18} aria-hidden="true" /> Coding platforms
            </h2>
            {githubAccount === null && codingProfiles.length === 0 ? (
              <p className="rounded-2xl border border-dashed border-rule p-6 text-center text-sm text-slate-500">
                No coding accounts connected yet.
              </p>
            ) : (
              <div className="space-y-2">
                {githubAccount ? (
                  <div className="flex items-center justify-between rounded-2xl border border-rule bg-white p-3.5">
                    <span className="text-sm text-ink">GitHub — {githubAccount.github_username}</span>
                    <VerificationBadge status={githubAccount.verification_status} />
                  </div>
                ) : null}
                {codingProfiles.map((account) => (
                  <div key={account.id} className="flex items-center justify-between rounded-2xl border border-rule bg-white p-3.5">
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
            <h2 className="mb-3 font-display text-lg font-semibold text-ink">Certificates</h2>
            {certificateList.length === 0 ? (
              <p className="rounded-2xl border border-dashed border-rule p-6 text-center text-sm text-slate-500">
                No certificates added yet.
              </p>
            ) : (
              <div className="space-y-2">
                {certificateList.map((cert) => (
                  <div key={cert.id} className="flex items-center justify-between rounded-2xl border border-rule bg-white p-3.5">
                    <span className="text-sm text-ink">
                      {cert.title} <span className="text-slate-400">· {cert.issuer}</span>
                    </span>
                    <VerificationBadge status={cert.verification_status} />
                  </div>
                ))}
              </div>
            )}
          </section>

          {Object.entries(analytics.data?.application_outcomes ?? {}).some(([, count]) => count > 0) ? (
            <section>
              <h2 className="mb-3 font-display text-lg font-semibold text-ink">Application outcomes</h2>
              <div className="flex flex-wrap gap-2">
                {Object.entries(analytics.data?.application_outcomes ?? {})
                  .filter(([, count]) => count > 0)
                  .map(([status, count]) => (
                    <Badge key={status} variant="neutral">
                      {status.replace(/_/g, " ")}: {count}
                    </Badge>
                  ))}
              </div>
            </section>
          ) : null}
        </div>
      </div>
    </div>
  );
}
