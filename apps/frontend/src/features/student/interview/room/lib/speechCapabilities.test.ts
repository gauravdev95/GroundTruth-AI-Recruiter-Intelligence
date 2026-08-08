import { describe, expect, it } from "vitest";

import { isSubstantiveUtterance, meaningfulWords } from "./speechCapabilities";

/**
 * The end-of-utterance gate.
 *
 * This is the one piece of logic in the room that can silently lose a
 * candidate's answer, so it is the one piece with tests. Too strict and a real
 * short answer is swallowed and the interviewer never replies; too loose and a
 * cough submits an empty turn to `service.advance`.
 */

describe("meaningfulWords", () => {
  it("drops the sounds people make while thinking", () => {
    expect(meaningfulWords("um, so, like, yeah")).toEqual([]);
  });

  it("keeps technical content that filler happens to surround", () => {
    expect(meaningfulWords("um, so we used Redis for caching")).toEqual([
      "we",
      "used",
      "redis",
      "for",
      "caching",
    ]);
  });

  it("keeps hyphenated and apostrophised words whole", () => {
    expect(meaningfulWords("it's write-through")).toEqual(["it's", "write-through"]);
  });

  it("is not confused by punctuation a recogniser inserts", () => {
    expect(meaningfulWords("Postgres, mainly. Redis too!")).toEqual([
      "postgres",
      "mainly",
      "redis",
      "too",
    ]);
  });
});

describe("isSubstantiveUtterance", () => {
  it.each([
    ["umm"],
    ["hmm..."],
    ["uh, um"],
    ["so"],
    ["okay"],
    [""],
    ["   "],
  ])("treats %j as the candidate still thinking", (text) => {
    expect(isSubstantiveUtterance(text)).toBe(false);
  });

  it.each([
    ["yes, exactly"],
    ["the message queue"],
    ["we used Redis for caching"],
    ["um, I think it was the retry decorator"],
  ])("treats %j as a finished answer", (text) => {
    expect(isSubstantiveUtterance(text)).toBe(true);
  });

  it("accepts a short real answer rather than swallowing it", () => {
    // The asymmetry this encodes: waiting one extra turn on a thin answer is
    // recoverable — the graph probes it. Swallowing a true short answer leaves
    // the candidate talking to an interviewer that has stopped responding.
    expect(isSubstantiveUtterance("Postgres, mainly")).toBe(true);
  });

  it("does not let a single long filler word through on length alone", () => {
    expect(isSubstantiveUtterance("hmmmmmmmmmmmm")).toBe(false);
  });
});
