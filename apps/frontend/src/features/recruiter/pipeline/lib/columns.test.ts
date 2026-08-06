import { describe, expect, it } from "vitest";

import type { PipelineBoard } from "../api/pipelineApi";
import { ALLOWED_MOVES, canMove, columnFor, summarise } from "./columns";
import { boardToCsv } from "./exportCsv";

function emptyBoard(): PipelineBoard {
  return {
    matched: [],
    applied: [],
    shortlisted: [],
    interview_scheduled: [],
    hired: [],
    rejected: [],
  };
}

describe("canMove", () => {
  it("mirrors the server's forward path one step at a time", () => {
    expect(canMove("applied", "shortlisted")).toBe(true);
    expect(canMove("shortlisted", "interview_scheduled")).toBe(true);
    expect(canMove("interview_scheduled", "hired")).toBe(true);
  });

  it("refuses to skip a stage", () => {
    expect(canMove("applied", "interview_scheduled")).toBe(false);
    expect(canMove("applied", "hired")).toBe(false);
  });

  it("allows closing from every non-terminal stage", () => {
    expect(canMove("applied", "rejected")).toBe(true);
    expect(canMove("shortlisted", "rejected")).toBe(true);
    expect(canMove("interview_scheduled", "rejected")).toBe(true);
  });

  it("treats hired and rejected as terminal", () => {
    expect(ALLOWED_MOVES.hired).toEqual([]);
    expect(ALLOWED_MOVES.rejected).toEqual([]);
  });

  it("never offers a backwards move — rollback is its own action", () => {
    expect(canMove("shortlisted", "applied")).toBe(false);
    expect(canMove("interview_scheduled", "shortlisted")).toBe(false);
  });
});

describe("columnFor", () => {
  it("collapses both outcomes onto the shared final column", () => {
    expect(columnFor("hired")).toBe("closed");
    expect(columnFor("rejected")).toBe("closed");
  });

  it("leaves every other stage in its own column", () => {
    expect(columnFor("applied")).toBe("applied");
    expect(columnFor("interview_scheduled")).toBe("interview_scheduled");
  });
});

describe("summarise", () => {
  it("drops zero-count segments so the numbers that matter stay findable", () => {
    const board = emptyBoard();
    board.matched = Array.from({ length: 14 }, (_, i) => ({
      candidate_profile_id: `c${i}`,
      headline: null,
      match_score: 60,
      matched_skills: [],
      reasoning: "",
      is_verified: false,
    }));
    expect(summarise(board)).toBe("14 matched");
  });

  it("says so plainly when the board is empty", () => {
    expect(summarise(emptyBoard())).toBe("No candidates yet");
  });
});

describe("boardToCsv", () => {
  it("quotes a reasoning string containing commas without splitting the row", () => {
    // The reasoning string contains commas by construction ("Matches on Rust,
    // PostgreSQL, …"), so unquoted output would silently shift every later
    // column on the row.
    const board = emptyBoard();
    board.matched = [
      {
        candidate_profile_id: "c1",
        headline: "Backend engineer",
        match_score: 87.4,
        matched_skills: ["Rust", "PostgreSQL"],
        reasoning: "Matches on Rust, PostgreSQL — 2 of 3 must-have skills verified",
        is_verified: true,
      },
    ];
    const rows = boardToCsv(board).split("\r\n");
    expect(rows).toHaveLength(2);
    expect(rows[1]).toContain('"Matches on Rust, PostgreSQL — 2 of 3 must-have skills verified"');
    expect(rows[1]).toContain('"87"');
  });

  it("escapes an embedded quote by doubling it", () => {
    const board = emptyBoard();
    board.matched = [
      {
        candidate_profile_id: "c1",
        headline: 'The "growth" engineer',
        match_score: 51,
        matched_skills: [],
        reasoning: "",
        is_verified: false,
      },
    ];
    expect(boardToCsv(board)).toContain('"The ""growth"" engineer"');
  });

  it("carries no candidate name, because the board never receives one", () => {
    expect(boardToCsv(emptyBoard()).split("\r\n")[0]).not.toContain("name");
  });
});
