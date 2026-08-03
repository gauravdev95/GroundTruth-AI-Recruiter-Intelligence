import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { makeSetupState } from "@/test/renderWithProviders";

import { SetupStepper } from "./SetupStepper";

/**
 * The stepper renders server values and derives nothing. These tests exist to
 * keep it that way — every assertion below reads a number or a status straight
 * off the fixture, so a client-side recomputation would break them.
 */
describe("SetupStepper", () => {
  it("renders the five spec labels in order", () => {
    const state = makeSetupState();
    render(
      <SetupStepper
        steps={state.steps}
        currentStepIndex={state.current_step_index}
        completionPercentage={state.completion_percentage}
      />,
    );

    const list = screen.getByRole("list");
    const titles = within(list)
      .getAllByRole("listitem")
      .map((item) => item.textContent);

    expect(titles[0]).toContain("Basic Information");
    expect(titles[0]).toContain("Personal details & education");
    expect(titles[1]).toContain("Technical Profiles");
    expect(titles[2]).toContain("Projects");
    expect(titles[3]).toContain("Certificates & Achievements");
    expect(titles[4]).toContain("Experience");
  });

  it("marks the active step from current_step_index, not from the statuses", () => {
    const state = makeSetupState({ current_step_index: 2 });
    render(
      <SetupStepper
        steps={state.steps}
        currentStepIndex={state.current_step_index}
        completionPercentage={state.completion_percentage}
      />,
    );

    // Scoped to the desktop list: the compact mobile indicator also names the
    // active step, and both are in the DOM at once under jsdom (only CSS hides
    // one). An unscoped query would match twice.
    const list = within(screen.getByRole("list"));
    const active = list.getByText("Projects").closest("[aria-current]");
    expect(active).toHaveAttribute("aria-current", "step");
    expect(screen.getAllByText("Current Step")).toHaveLength(1);
  });

  it("puts the Current Step pill under the active step only", () => {
    const state = makeSetupState({ current_step_index: 1 });
    render(
      <SetupStepper
        steps={state.steps}
        currentStepIndex={state.current_step_index}
        completionPercentage={state.completion_percentage}
      />,
    );

    const items = screen.getAllByRole("listitem");
    expect(within(items[1]).getByText("Current Step")).toBeInTheDocument();
    expect(within(items[0]).queryByText("Current Step")).not.toBeInTheDocument();
  });

  it("renders the completion percentage the server sent", () => {
    const state = makeSetupState({ completion_percentage: 65, current_step_index: 2 });
    render(
      <SetupStepper
        steps={state.steps}
        currentStepIndex={state.current_step_index}
        completionPercentage={state.completion_percentage}
      />,
    );

    expect(screen.getByText("65% Complete")).toBeInTheDocument();
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "65");
  });

  it("keeps filled and verified distinct for screen readers", () => {
    const base = makeSetupState({ current_step_index: 0 });
    const steps = base.steps.map((step, index) =>
      index === 1
        ? { ...step, status: "saved" as const }
        : index === 2
          ? { ...step, status: "verified" as const }
          : index === 3
            ? { ...step, status: "pending_verification" as const }
            : step,
    );

    render(<SetupStepper steps={steps} currentStepIndex={0} completionPercentage={40} />);

    const items = screen.getAllByRole("listitem");
    expect(within(items[1]).getByText("Saved")).toBeInTheDocument();
    expect(within(items[2]).getByText("Verified")).toBeInTheDocument();
    expect(within(items[3]).getByText("Saved, verification in progress")).toBeInTheDocument();
    expect(within(items[4]).getByText(/Not started/)).toBeInTheDocument();
  });

  it("collapses to a Step N of 5 indicator for small viewports", () => {
    const state = makeSetupState({ current_step_index: 3, completion_percentage: 45 });
    render(
      <SetupStepper
        steps={state.steps}
        currentStepIndex={state.current_step_index}
        completionPercentage={state.completion_percentage}
      />,
    );

    expect(screen.getByText("Step 4 of 5")).toBeInTheDocument();
  });

  it("makes every step selectable — the index is a hint, never a gate", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    const state = makeSetupState({ current_step_index: 0 });

    render(
      <SetupStepper
        steps={state.steps}
        currentStepIndex={0}
        completionPercentage={0}
        onSelect={onSelect}
      />,
    );

    // Step 5 is empty and four steps ahead of the current one; it must still
    // be reachable, because the builder is a multi-sitting flow.
    await user.click(screen.getByRole("button", { name: /Step 5: Experience/ }));
    expect(onSelect).toHaveBeenCalledWith(expect.objectContaining({ key: "experience" }));
  });
});
