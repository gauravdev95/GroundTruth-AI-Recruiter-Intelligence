import type { RadarAxis } from "@/components/charts/SkillRadar";

import type { EvidenceRecord } from "../api/evidenceApi";

/** Where the benchmark ring sits for a must-have versus a nice-to-have.
 *
 * These two constants are the *requirement tier*, not an invented proficiency
 * target. The evidence record carries which half of `match_reasons` a skill
 * came from (required or desirable) but not the `min_proficiency` the
 * recruiter confirmed — that lives on `job_requirements`, which this endpoint
 * does not join. Rather than guess a percentage per skill, the ring says the
 * one thing that *is* known: this skill is required, or it is a bonus. The
 * bars directly under the chart carry the exact evidence weights.
 */
const MUST_HAVE_BENCHMARK = 100;
const NICE_TO_HAVE_BENCHMARK = 50;

/** Its own module rather than living beside the tab components, so that file
 * exports only components and keeps react-refresh happy. */
export function buildRadarAxes(record: EvidenceRecord): RadarAxis[] {
  if (!record.match) return [];

  const axes: RadarAxis[] = [];
  for (const skill of record.match.matched_required_skills) {
    axes.push({
      skill: skill.skill_name,
      candidate: Math.round((skill.evidence_weight ?? 0) * 100),
      required: MUST_HAVE_BENCHMARK,
    });
  }
  for (const skill of record.match.matched_desirable_skills) {
    axes.push({
      skill: skill.skill_name,
      candidate: Math.round((skill.evidence_weight ?? 0) * 100),
      required: NICE_TO_HAVE_BENCHMARK,
    });
  }
  return axes;
}
