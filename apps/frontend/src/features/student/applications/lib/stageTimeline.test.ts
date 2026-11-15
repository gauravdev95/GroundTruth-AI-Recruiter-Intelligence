import { describe, expect, it } from "vitest";

import { buildStageTimeline } from "./stageTimeline";

const APPLIED_AT = "2026-11-01T09:00:00Z";
const UPDATED_AT = "2026-11-05T12:00:00Z";

describe("buildStageTimeline", () => {
  it("marks earlier stages done and the current stage current", () => {
    const stages = buildStageTimeline("interview_scheduled", APPLIED_AT, UPDATED_AT);
    expect(stages.map((s) => s.state)).toEqual(["done", "done", "current", "upcoming"]);
    // Intermediate stages carry no date: none is recorded for them.
    expect(stages[0].date).toBeUndefined();
    expect(stages[2].dateLabel).toBe("Updated");
    expect(stages[2].date).toContain("2026");
  });

  it("shows only the applied date for a fresh application", () => {
    const stages = buildStageTimeline("applied", APPLIED_AT, UPDATED_AT);
    expect(stages.map((s) => s.state)).toEqual(["current", "upcoming", "upcoming", "upcoming"]);
    expect(stages[0].dateLabel).toBe("Applied");
  });

  it("marks every stage done when hired", () => {
    const stages = buildStageTimeline("hired", APPLIED_AT, UPDATED_AT);
    expect(stages.map((s) => s.state)).toEqual(["done", "done", "done", "current"]);
  });

  it("never invents intermediate stages for a rejection", () => {
    const stages = buildStageTimeline("rejected", APPLIED_AT, UPDATED_AT);
    expect(stages).toHaveLength(2);
    expect(stages.map((s) => s.label)).toEqual(["Applied", "Not selected"]);
    expect(stages[1].dateLabel).toBe("Decision");
  });
});
