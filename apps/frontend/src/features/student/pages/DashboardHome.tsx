import { ArrowRight, Award, Briefcase, CheckCircle2, Eye, GitBranch, ListChecks } from "lucide-react";
import { Link } from "react-router-dom";

import { Card, EmptyState, ErrorState, Skeleton } from "@/components";
import { Reveal, Stagger, Surface } from "@/design";
import { useAuthContext } from "@/features/auth";
import { DeadLetterBanner } from "@/features/jobs";

import { useStudentAnalytics } from "../analytics/hooks/useStudentAnalytics";
import type { SectionKey } from "../api/profileApi";
import { ActivityTimeline } from "../components/ActivityTimeline";
import { OutcomesChart } from "../components/OutcomesChart";
import { ProfileStrengthMeter } from "../components/ProfileStrengthMeter";
import { RepoEvidenceCard } from "../components/RepoEvidenceCard";
import { VerificationBadge } from "../components/SectionBadges";
import { useCertificatesSection, useProfileCompleteness, useProjectsSection, useTechnicalSection } from "../hooks/useProfileSection";
import { JobFeedPreview } from "../matches/components/JobFeedPreview";
import { SmartApplyPrompts } from "../matches/components/SmartApplyPrompts";

/** Completeness scores six sections; the builder edits five forms — GitHub
 * and coding profiles share the technical form. Actions point at the builder,
 * where the stepper picks the right form. */
const SECTION_TITLES: Record<SectionKey, string> = {
  basic: "Basic information",
  github: "Technical verification",
  projects: "Skills & projects",
  coding: "Technical verification",
  certificates: "Certificates & achievements",
  experience: "Experience",
};

function StatCard({
  icon: Icon,
  label,
  value,
  hint,
}: {
  icon: typeof Briefcase;
  label: string;
  value: number | string;
  hint: string;
}) {
  return (
    <Surface className="p-4 sm:p-5">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-2xl font-semibold tabular-nums text-[var(--ink)]">{value}</p>
          <p className="mt-0.5 truncate text-sm font-medium text-[var(--ink)]">{label}</p>
          <p className="mt-0.5 text-xs text-[var(--slate)]">{hint}</p>
        </div>
        <span
          aria-hidden="true"
          className="flex h-10 w-10 shrink-0 items-center justify-center rounded-[var(--r-md)] bg-[var(--violet)]/10 text-[var(--violet)]"
        >
          <Icon size={18} />
        </span>
      </div>
    </Surface>
  );
}

/** The real candidate dashboard home: profile strength breakdown, per-claim
 * verification status, repo evidence cards, coding-platform stats,
 * certificate status, and match count — every number read straight from the
 * server, nothing recomputed client-side (same principle as the job feed). */
export function DashboardHome() {
  const { user } = useAuthContext();
  const completeness = useProfileCompleteness();
  const technical = useTechnicalSection();
  const projects = useProjectsSection();
  const certificates = useCertificatesSection();
  const analytics = useStudentAnalytics();

  if (completeness.isPending || technical.isPending || projects.isPending || certificates.isPending) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-16 w-full max-w-md" />
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {[0, 1, 2, 3].map((index) => (
            <Skeleton key={index} className="h-24 w-full" />
          ))}
        </div>
        <div className="grid gap-4 lg:grid-cols-[minmax(0,320px)_1fr]">
          <Skeleton className="h-64 w-full" />
          <Skeleton className="h-64 w-full" />
        </div>
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
  const outcomes = analytics.data?.application_outcomes ?? {};
  const applicationsSent = Object.values(outcomes).reduce((a, b) => a + b, 0);
  const verifiedRepos = projectList.filter((project) => project.verification_status === "verified").length;

  const firstName = (user?.full_name ?? "").trim().split(/\s+/)[0] ?? "";
  const today = new Date().toLocaleDateString(undefined, {
    weekday: "long",
    month: "long",
    day: "numeric",
  });

  // Next steps, derived from the server's own completeness report — never a
  // hardcoded checklist. Only sections the server says are incomplete appear.
  const openSections = completeness.data.sections.filter((section) => !section.is_complete);
  const allComplete = openSections.length === 0;

  return (
    <div className="space-y-6">
      <Reveal trigger="mount">
        <header>
          <p className="text-xs font-semibold uppercase tracking-[var(--tracking-overline)] text-[var(--muted)]">
            {today}
          </p>
          <h1 className="mt-1 font-display text-2xl font-semibold text-[var(--ink)] sm:text-[var(--fs-h1)]">
            Welcome back{firstName ? `, ${firstName}` : ""}
          </h1>
          <p className="mt-1 text-sm text-[var(--slate)]">
            {completeness.data.is_discoverable
              ? "Your profile is discoverable to recruiters."
              : completeness.data.meets_section_requirements
                ? "Both required sections are done — we're indexing your profile now."
                : "Complete the required sections to become discoverable to recruiters."}
          </p>
        </header>
      </Reveal>

      <DeadLetterBanner />

      {/* Above the stat tiles, not inside the feed column: a Tier B match is
          the one thing on this page that asks the student to *act*, and
          burying an action under four sections of status is how it gets
          missed. Renders nothing when there are no Tier B matches. */}
      <SmartApplyPrompts />

      <Stagger className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Stagger.Item>
          <StatCard icon={Briefcase} label="Job matches" value={analytics.data?.match_count ?? 0} hint="Roles matched to your profile" />
        </Stagger.Item>
        <Stagger.Item>
          <StatCard icon={Eye} label="Profile views" value={analytics.data?.profile_views ?? 0} hint="Views by recruiters" />
        </Stagger.Item>
        <Stagger.Item>
          <StatCard icon={Award} label="Applications sent" value={applicationsSent} hint="Across all applications" />
        </Stagger.Item>
        <Stagger.Item>
          <StatCard
            icon={GitBranch}
            label="Verified repositories"
            value={`${verifiedRepos} of ${projectList.length}`}
            hint={projectList.length === 0 ? "No repositories linked yet" : "Passed repository verification"}
          />
        </Stagger.Item>
      </Stagger>

      <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,320px)_minmax(0,1fr)]">
        <div className="space-y-6">
          <ProfileStrengthMeter completeness={completeness.data} />

          <Card
            title="Recommended actions"
            subtitle={allComplete ? "Nothing outstanding — your profile is complete." : "The fastest way to strengthen your profile."}
          >
            {allComplete ? (
              <p className="flex items-start gap-2 text-sm text-[var(--slate)]">
                <CheckCircle2 size={16} className="mt-0.5 shrink-0 text-[var(--verified)]" aria-hidden="true" />
                Every section is complete. Adding certificates or experience still raises your
                profile strength.
              </p>
            ) : (
              <ul className="space-y-2">
                {openSections.map((section) => (
                  <li key={section.key}>
                    <Link
                      to="/student/profile"
                      className="group flex items-center justify-between gap-3 rounded-[var(--r-md)] border border-[var(--rule)] bg-[var(--panel)] px-3.5 py-3 transition hover:border-[var(--violet)]/50"
                    >
                      <span className="min-w-0">
                        <span className="flex items-center gap-2 text-sm font-medium text-[var(--ink)]">
                          <ListChecks size={15} className="shrink-0 text-[var(--violet)]" aria-hidden="true" />
                          Complete {SECTION_TITLES[section.key]}
                        </span>
                        <span className="mt-0.5 block truncate text-xs text-[var(--slate)]">
                          {section.missing.length > 0
                            ? section.missing.slice(0, 2).join(" · ")
                            : `${section.points_earned}/${section.points_possible} points`}
                        </span>
                      </span>
                      <ArrowRight
                        size={15}
                        className="shrink-0 text-[var(--muted)] transition group-hover:translate-x-0.5 group-hover:text-[var(--ink)]"
                        aria-hidden="true"
                      />
                    </Link>
                  </li>
                ))}
              </ul>
            )}
            <p className="mt-4 border-t border-[var(--rule-soft)] pt-3 text-xs text-[var(--slate)]">
              <Link to="/student/resume" className="font-medium text-[var(--ink)] hover:underline">
                Import or update your resume
              </Link>{" "}
              to pre-fill any section from a PDF or DOCX.
            </p>
          </Card>

          <ActivityTimeline />
        </div>

        <div className="min-w-0 space-y-6">
          {/* The ranked feed lives here as well as on its own page: the flow
              names it as dashboard content, and a student who lands here
              should see what they matched to without a second navigation. */}
          <Card
            title="Your job matches"
            subtitle="Roles ranked against your verified profile."
            actions={
              <Link
                to="/student/matches"
                className="inline-flex items-center gap-1 text-sm font-medium text-[var(--ink)] hover:underline"
              >
                View all <ArrowRight size={14} aria-hidden="true" />
              </Link>
            }
          >
            <JobFeedPreview />
          </Card>

          <OutcomesChart outcomes={outcomes} />

          <Card
            title="Repositories"
            subtitle="Linked repositories and their verification status."
            actions={
              <Link to="/student/profile" className="text-sm font-medium text-[var(--ink)] hover:underline">
                Manage
              </Link>
            }
          >
            {projectList.length === 0 ? (
              <EmptyState
                title="No repositories added yet"
                description="Link a repository from your GitHub account and we'll verify your authorship."
                action={
                  <Link to="/student/profile" className="font-medium text-[var(--ink)] hover:underline">
                    Add one in your profile
                  </Link>
                }
              />
            ) : (
              <div className="grid gap-3 sm:grid-cols-2">
                {projectList.map((project) => (
                  <RepoEvidenceCard key={project.id} project={project} />
                ))}
              </div>
            )}
          </Card>

          <Card title="Coding platforms" subtitle="Connected accounts and their verification status.">
            {githubAccount === null && codingProfiles.length === 0 ? (
              <EmptyState
                title="No coding accounts connected yet"
                description="Connect GitHub and add your coding-platform handles so recruiters can see verified evidence of your work."
              />
            ) : (
              <ul className="space-y-2">
                {githubAccount ? (
                  <li className="flex items-center justify-between gap-3 rounded-[var(--r-md)] border border-[var(--rule)] bg-[var(--panel)] p-3.5">
                    <span className="min-w-0 truncate text-sm text-[var(--ink)]">
                      GitHub — <span className="machine">{githubAccount.github_username}</span>
                    </span>
                    <VerificationBadge status={githubAccount.verification_status} />
                  </li>
                ) : null}
                {codingProfiles.map((account) => (
                  <li
                    key={account.id}
                    className="flex items-center justify-between gap-3 rounded-[var(--r-md)] border border-[var(--rule)] bg-[var(--panel)] p-3.5"
                  >
                    <span className="min-w-0 truncate text-sm capitalize text-[var(--ink)]">
                      {account.platform} — <span className="machine">{account.handle}</span>
                    </span>
                    <VerificationBadge status={account.verification_status} />
                  </li>
                ))}
              </ul>
            )}
          </Card>

          <Card title="Certificates" subtitle="Credentials on your profile and their verification status.">
            {certificateList.length === 0 ? (
              <EmptyState
                title="No certificates added yet"
                description="Add a certificate with its issuer and a link or file, and we'll check it."
              />
            ) : (
              <ul className="space-y-2">
                {certificateList.map((cert) => (
                  <li
                    key={cert.id}
                    className="flex items-center justify-between gap-3 rounded-[var(--r-md)] border border-[var(--rule)] bg-[var(--panel)] p-3.5"
                  >
                    <span className="min-w-0 truncate text-sm text-[var(--ink)]">
                      {cert.title} <span className="text-[var(--muted)]">· {cert.issuer}</span>
                    </span>
                    <VerificationBadge status={cert.verification_status} />
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
}
