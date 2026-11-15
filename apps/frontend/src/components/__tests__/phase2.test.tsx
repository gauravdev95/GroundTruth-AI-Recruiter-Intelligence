import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { Badge } from "@/components/Badge";
import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { Dropdown } from "@/components/Dropdown";
import { Pagination } from "@/components/Pagination";
import { Table, TableBody, TableCell, TableHead, TableHeaderCell, TableRow } from "@/components/Table";
import { Tabs } from "@/components/Tabs";
import { Textarea } from "@/components/Textarea";
import { ThemeToggle } from "@/components/ThemeToggle";
import { Tooltip } from "@/components/Tooltip";
import { renderWithProviders } from "@/test/renderWithProviders";

/**
 * Phase 2 global components. These tests pin behaviour, not styling: the
 * keyboard contract of the menu and the tabs, the pager's window, the
 * dialog's confirm/cancel wiring, and the theme toggle's `[data-theme]`
 * write. A restyle that keeps those contracts passes; a restyle that
 * breaks one fails here first.
 */
describe("Badge", () => {
  it("renders the verification vocabulary as distinct variants", () => {
    render(
      <>
        <Badge variant="verified">VERIFIED</Badge>
        <Badge variant="flagged">FLAGGED</Badge>
        <Badge variant="rejected">REJECTED</Badge>
      </>,
    );
    expect(screen.getByText("VERIFIED")).toBeInTheDocument();
    expect(screen.getByText("FLAGGED")).toBeInTheDocument();
    expect(screen.getByText("REJECTED")).toBeInTheDocument();
  });
});

describe("Button", () => {
  it("renders the danger variant and announces a loading state", () => {
    render(
      <Button variant="danger" isLoading>
        Delete
      </Button>,
    );
    const button = screen.getByRole("button", { name: "Delete" });
    expect(button).toBeDisabled();
    expect(button).toHaveAttribute("aria-busy", "true");
  });
});

describe("Textarea", () => {
  it("wires label, hint and error to the field", () => {
    const { rerender } = render(
      <Textarea label="Summary" hint="Two sentences, max." />,
    );
    const field = screen.getByLabelText("Summary");
    expect(field).toHaveAttribute("aria-describedby", expect.stringContaining("hint"));

    rerender(<Textarea label="Summary" hint="Two sentences, max." error="Required" />);
    expect(screen.getByRole("alert")).toHaveTextContent("Required");
    expect(screen.queryByText("Two sentences, max.")).not.toBeInTheDocument();
  });
});

describe("Card", () => {
  it("renders a title, subtitle and actions over Surface", () => {
    render(
      <Card title="Matches" subtitle="Ranked by evidence" actions={<button type="button">View all</button>}>
        <p>Body</p>
      </Card>,
    );
    expect(screen.getByText("Matches")).toBeInTheDocument();
    expect(screen.getByText("Ranked by evidence")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "View all" })).toBeInTheDocument();
    expect(screen.getByText("Body")).toBeInTheDocument();
  });
});

describe("Dropdown", () => {
  const items = [
    { id: "edit", label: "Edit", onSelect: vi.fn() },
    { id: "delete", label: "Delete", danger: true, onSelect: vi.fn() },
  ];

  function renderDropdown() {
    return render(
      <Dropdown
        trigger={(props) => (
          <button type="button" {...props}>
            Actions
          </button>
        )}
        items={items}
      />,
    );
  }

  it("opens on click, selects an item, and closes", async () => {
    const user = userEvent.setup();
    renderDropdown();

    await user.click(screen.getByRole("button", { name: "Actions" }));
    expect(screen.getByRole("menu")).toBeInTheDocument();

    await user.click(screen.getByRole("menuitem", { name: "Edit" }));
    expect(items[0].onSelect).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole("menu")).not.toBeInTheDocument();
  });

  it("moves with arrow keys and closes on Escape", async () => {
    const user = userEvent.setup();
    renderDropdown();

    await user.click(screen.getByRole("button", { name: "Actions" }));
    await user.keyboard("{ArrowDown}");
    expect(screen.getByRole("menuitem", { name: "Edit" })).toHaveFocus();
    await user.keyboard("{ArrowDown}");
    expect(screen.getByRole("menuitem", { name: "Delete" })).toHaveFocus();
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("menu")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Actions" })).toHaveFocus();
  });
});

describe("Tabs", () => {
  const tabs = [
    { id: "all", label: "All", count: 3 },
    { id: "saved", label: "Saved" },
    { id: "archived", label: "Archived", disabled: true },
  ];

  it("selects on click and moves with arrow keys, skipping disabled tabs", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<Tabs tabs={tabs} onChange={onChange} />);

    expect(screen.getByRole("tab", { name: /All/ })).toHaveAttribute("aria-selected", "true");

    await user.click(screen.getByRole("tab", { name: "Saved" }));
    expect(onChange).toHaveBeenCalledWith("saved");

    await user.keyboard("{ArrowRight}");
    // Right from "Saved" skips the disabled "Archived" and wraps to "All".
    expect(screen.getByRole("tab", { name: /All/ })).toHaveFocus();
    expect(onChange).toHaveBeenCalledWith("all");
  });
});

describe("Table", () => {
  it("renders a real table with a sortable header", async () => {
    const user = userEvent.setup();
    const onSort = vi.fn();
    render(
      <Table>
        <TableHead>
          <TableRow>
            <TableHeaderCell sort="asc" onSort={onSort}>
              Score
            </TableHeaderCell>
          </TableRow>
        </TableHead>
        <TableBody>
          <TableRow>
            <TableCell>84</TableCell>
          </TableRow>
        </TableBody>
      </Table>,
    );

    const table = screen.getByRole("table");
    expect(within(table).getByText("84")).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Score" })).toHaveAttribute(
      "aria-sort",
      "ascending",
    );

    await user.click(screen.getByRole("button", { name: "Score" }));
    expect(onSort).toHaveBeenCalledTimes(1);
  });
});

describe("Pagination", () => {
  it("renders nothing for a single page and a window with ellipsis for many", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();

    const { rerender } = render(<Pagination page={1} totalPages={1} onChange={onChange} />);
    expect(screen.queryByRole("navigation", { name: "Pagination" })).not.toBeInTheDocument();

    rerender(<Pagination page={5} totalPages={10} onChange={onChange} />);
    const nav = screen.getByRole("navigation", { name: "Pagination" });
    expect(within(nav).getByRole("button", { name: "Page 5, current page" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    // First and last pages are always reachable; the gap is an ellipsis.
    expect(within(nav).getByRole("button", { name: "Go to page 1" })).toBeInTheDocument();
    expect(within(nav).getByRole("button", { name: "Go to page 10" })).toBeInTheDocument();

    await user.click(within(nav).getByRole("button", { name: "Go to page 6" }));
    expect(onChange).toHaveBeenCalledWith(6);
  });
});

describe("Tooltip", () => {
  it("shows its content on hover and describes the trigger", async () => {
    const user = userEvent.setup();
    render(
      <Tooltip content="Proven by an artefact">
        <button type="button">Verified</button>
      </Tooltip>,
    );

    const trigger = screen.getByRole("button", { name: "Verified" });
    await user.hover(trigger);
    expect(screen.getByRole("tooltip")).toHaveTextContent("Proven by an artefact");
    expect(trigger).toHaveAttribute("aria-describedby");
  });
});

describe("ConfirmDialog", () => {
  it("confirms and cancels without closing itself on confirm", async () => {
    const user = userEvent.setup();
    const onConfirm = vi.fn();
    const onClose = vi.fn();
    render(
      <ConfirmDialog
        open
        onClose={onClose}
        onConfirm={onConfirm}
        title="Withdraw application?"
        description="This cannot be undone."
        tone="danger"
        confirmLabel="Withdraw"
      />,
    );

    expect(screen.getByRole("dialog")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Withdraw" }));
    expect(onConfirm).toHaveBeenCalledTimes(1);
    // The dialog does not close itself: the caller closes it after its
    // action completes.
    expect(onClose).not.toHaveBeenCalled();

    await user.click(screen.getByRole("button", { name: "Cancel" }));
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});

describe("ThemeToggle", () => {
  it("writes the explicit choice to [data-theme] and persists it", async () => {
    const user = userEvent.setup();
    document.documentElement.removeAttribute("data-theme");
    window.localStorage.clear();

    renderWithProviders(<ThemeToggle />);

    // jsdom has no prefers-color-scheme match, so the resolved theme starts dark.
    const toggle = screen.getByRole("button", { name: "Switch to light theme" });
    await user.click(toggle);

    expect(document.documentElement.getAttribute("data-theme")).toBe("light");
    expect(window.localStorage.getItem("gt-theme")).toBe("light");
    expect(screen.getByRole("button", { name: "Switch to dark theme" })).toBeInTheDocument();

    document.documentElement.removeAttribute("data-theme");
    window.localStorage.clear();
  });
});
