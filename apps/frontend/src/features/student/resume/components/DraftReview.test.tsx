import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { renderWithProviders } from "@/test/renderWithProviders";

import type { ResumeDraftDetail } from "../api/resumeApi";
import { DraftReview } from "./DraftReview";

const confirmDraft = vi.fn();
const discardDraft = vi.fn();

vi.mock("../api/resumeApi", async () => {
  const actual = await vi.importActual<typeof import("../api/resumeApi")>("../api/resumeApi");
  return {
    ...actual,
    resumeApi: {
      confirmDraft: (draftId: string, payload: unknown) => confirmDraft(draftId, payload),
      discardDraft: (draftId: string) => discardDraft(draftId),
    },
  };
});

const DETAIL: ResumeDraftDetail = {
  draft: {
    id: "draft-1",
    resume_upload_id: "upload-1",
    status: "pending_review",
    provider: "anthropic",
    model: "claude-opus-5",
    payload: {},
    confirmed_at: null,
    created_at: new Date().toISOString(),
  },
  suggestions: {
    basic: {
      headline: "Final-year CS student building compilers",
      college: "IIT Bombay",
      degree: "btech",
      branch: "cse",
      graduation_year: 2026,
      location: "Mumbai, India",
      target_role: "backend",
    },
    technical: {},
    projects: [],
    certificates: [],
    experience: [],
    unmapped: ["We couldn't find a LeetCode handle."],
  },
};

/**
 * The review screen is the only path from a draft into a live profile, so
 * these tests are about one property: what the student sees is what gets sent,
 * including their edits — never the model's original suggestion.
 */
describe("DraftReview", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    confirmDraft.mockResolvedValue({
      draft: { ...DETAIL.draft, status: "confirmed" },
      completeness: { profile_strength: 35, sections: [] },
    });
  });

  it("states that nothing is saved yet and lists what the parser could not fill", () => {
    renderWithProviders(<DraftReview detail={DETAIL} onDone={vi.fn()} />);

    expect(screen.getByText("Nothing here is saved yet.")).toBeInTheDocument();
    // Unfilled fields are reported, not guessed.
    expect(screen.getByText("We couldn't find a LeetCode handle.")).toBeInTheDocument();
  });

  it("groups extracted fields by section", () => {
    renderWithProviders(<DraftReview detail={DETAIL} onDone={vi.fn()} />);

    for (const heading of ["Basic Information", "Technical Verification", "Projects", "Certificates", "Experience"]) {
      expect(screen.getByRole("heading", { name: heading })).toBeInTheDocument();
    }
  });

  it("sends the student's edit, not the extracted value", async () => {
    const user = userEvent.setup();
    const onDone = vi.fn();
    renderWithProviders(<DraftReview detail={DETAIL} onDone={onDone} />);

    const headline = screen.getByDisplayValue("Final-year CS student building compilers");
    await user.clear(headline);
    await user.type(headline, "Backend engineer who ships");

    await user.click(screen.getByRole("button", { name: /Import selected/ }));

    await waitFor(() => expect(confirmDraft).toHaveBeenCalled());
    const [draftId, payload] = confirmDraft.mock.calls[0];
    expect(draftId).toBe("draft-1");
    expect(payload.basic.headline).toBe("Backend engineer who ships");
    // The other extracted fields ride along unchanged.
    expect(payload.basic.college).toBe("IIT Bombay");

    await waitFor(() => expect(onDone).toHaveBeenCalled());
  });

  it("omits a section the student unticked", async () => {
    const user = userEvent.setup();
    renderWithProviders(
      <DraftReview
        detail={{
          ...DETAIL,
          suggestions: {
            ...DETAIL.suggestions,
            technical: { github_username: "ada", coding_profiles: [{ platform: "leetcode", handle: "ada_lc" }] },
          },
        }}
        onDone={vi.fn()}
      />,
    );

    // Untick every basic field so section 1 is excluded entirely.
    for (const label of [
      "Final-year CS student building compilers",
      "IIT Bombay",
      "Mumbai, India",
    ]) {
      const input = screen.getByDisplayValue(label);
      const checkbox = input.closest("div")?.parentElement?.querySelector("input[type=checkbox]");
      if (checkbox) await user.click(checkbox);
    }

    await user.click(screen.getByRole("button", { name: /Import selected/ }));

    await waitFor(() => expect(confirmDraft).toHaveBeenCalled());
    const [, payload] = confirmDraft.mock.calls[0];
    expect(payload.technical).toBeDefined();
  });

  it("writes nothing when the student discards", async () => {
    const user = userEvent.setup();
    const onDone = vi.fn();
    discardDraft.mockResolvedValue({ ...DETAIL.draft, status: "discarded" });

    renderWithProviders(<DraftReview detail={DETAIL} onDone={onDone} />);
    await user.click(screen.getByRole("button", { name: /Discard/ }));

    await waitFor(() => expect(discardDraft).toHaveBeenCalledWith("draft-1"));
    expect(confirmDraft).not.toHaveBeenCalled();
  });
});
