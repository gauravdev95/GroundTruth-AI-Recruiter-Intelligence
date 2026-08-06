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
  it("renders the eight spec labels in order", () => {
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

    expect(titles[0]).toContain("Get Started");
    expect(titles[1]).toContain("Basic Information");
    expect(titles[1]).toContain("Personal details & education");
    // GitHub and the coding profile are separate steps now: only GitHub is
    // mandatory, and one combined step made the optional half look required.
    expect(titles[2]).toContain("Connect GitHub");
    expect(titles[3]).toContain("Link Projects");
    expect(titles[4]).toContain("Coding Profile");
    expect(titles[5]).toContain("Certificates");
    expect(titles[6]).toContain("Experience");
    expect(titles[7]).toContain("Review & Submit");
  });

  it("marks the active step from current_step_index, not from the statuses", () => {
    const state = makeSetupState({ current_step_index: 3 });
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
    const active = list.getByText("Link Projects").closest("[aria-current]");
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

    expect(screen.getByText("65% profile strength")).toBeInTheDocument();
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

  it("collapses to a Step N of 8 indicator for small viewports", () => {
    const state = makeSetupState({ current_step_index: 3, completion_percentage: 45 });
    render(
      <SetupStepper
        steps={state.steps}
        currentStepIndex={state.current_step_index}
        completionPercentage={state.completion_percentage}
      />,
    );

    expect(screen.getByText("Step 4 of 8")).toBeInTheDocument();
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

    // Step 7 is empty and six steps ahead of the current one; it must still
    // be reachable, because the flow is explicitly multi-sitting.
    await user.click(screen.getByRole("button", { name: /Step 7: Experience/ }));
    expect(onSelect).toHaveBeenCalledWith(expect.objectContaining({ key: "experience" }));
  });
});
