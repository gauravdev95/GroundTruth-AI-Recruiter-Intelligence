import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { MAX_RESUME_BYTES } from "../lib/validateResumeFile";
import { ResumeDropZone } from "./ResumeDropZone";

function makeFile(name: string, { size = 1024, type = "" } = {}): File {
  const file = new File(["x"], name, { type });
  // `File` has no writable size, and allocating 10 MB of real bytes per test
  // would be slow for a check that only reads the property.
  Object.defineProperty(file, "size", { value: size });
  return file;
}

/**
 * Put a file on the input and fire `change` directly.
 *
 * `user.upload` emulates the browser's `accept` filter and silently drops
 * anything it excludes, so it cannot exercise the component's own rejection
 * path at all — the very thing these tests are for. A real browser's filter is
 * also only a hint (drag-and-drop and "All files" both bypass it), so the
 * component must reject these regardless.
 */
function selectFile(input: HTMLInputElement, file: File) {
  Object.defineProperty(input, "files", { value: [file], configurable: true });
  fireEvent.change(input);
}

describe("ResumeDropZone", () => {
  it("accepts a PDF via the file picker", async () => {
    const user = userEvent.setup();
    const onFile = vi.fn();
    const onReject = vi.fn();

    const { container } = render(<ResumeDropZone onFile={onFile} onReject={onReject} />);
    const input = container.querySelector("input[type=file]") as HTMLInputElement;

    await user.upload(input, makeFile("ada.pdf", { type: "application/pdf" }));

    expect(onFile).toHaveBeenCalledWith(expect.objectContaining({ name: "ada.pdf" }));
    expect(onReject).not.toHaveBeenCalled();
  });

  it("rejects a legacy .doc with the specific remedy", () => {
    const onFile = vi.fn();
    const onReject = vi.fn();

    const { container } = render(<ResumeDropZone onFile={onFile} onReject={onReject} />);
    selectFile(
      container.querySelector("input[type=file]") as HTMLInputElement,
      makeFile("ada.doc", { type: "application/msword" }),
    );

    expect(onFile).not.toHaveBeenCalled();
    expect(onReject).toHaveBeenCalledWith("Legacy .doc isn't supported — save as PDF or DOCX");
  });

  it("rejects an unsupported type", () => {
    const onFile = vi.fn();
    const onReject = vi.fn();

    const { container } = render(<ResumeDropZone onFile={onFile} onReject={onReject} />);
    selectFile(
      container.querySelector("input[type=file]") as HTMLInputElement,
      makeFile("ada.txt", { type: "text/plain" }),
    );

    expect(onFile).not.toHaveBeenCalled();
    expect(onReject).toHaveBeenCalledWith(expect.stringContaining("isn't supported"));
  });

  it("rejects a file over the size ceiling before any upload starts", () => {
    const onFile = vi.fn();
    const onReject = vi.fn();

    const { container } = render(<ResumeDropZone onFile={onFile} onReject={onReject} />);
    selectFile(
      container.querySelector("input[type=file]") as HTMLInputElement,
      makeFile("huge.pdf", { size: MAX_RESUME_BYTES + 1 }),
    );

    expect(onFile).not.toHaveBeenCalled();
    expect(onReject).toHaveBeenCalledWith(expect.stringContaining("larger than 10 MB"));
  });

  it("accepts a dropped file", () => {
    const onFile = vi.fn();
    const onReject = vi.fn();

    render(<ResumeDropZone onFile={onFile} onReject={onReject} />);
    const zone = screen.getByRole("button", { name: /Upload your resume/ });
    const file = makeFile("ada.docx");

    fireEvent.drop(zone, { dataTransfer: { files: [file] } });

    expect(onFile).toHaveBeenCalledWith(expect.objectContaining({ name: "ada.docx" }));
  });

  it("rejects a dropped file of the wrong type without uploading it", () => {
    const onFile = vi.fn();
    const onReject = vi.fn();

    render(<ResumeDropZone onFile={onFile} onReject={onReject} />);
    fireEvent.drop(screen.getByRole("button", { name: /Upload your resume/ }), {
      dataTransfer: { files: [makeFile("photo.png", { type: "image/png" })] },
    });

    expect(onFile).not.toHaveBeenCalled();
    expect(onReject).toHaveBeenCalled();
  });

  it("is keyboard reachable and opens the picker on Enter", async () => {
    const user = userEvent.setup();
    const { container } = render(<ResumeDropZone onFile={vi.fn()} onReject={vi.fn()} />);

    const zone = screen.getByRole("button", { name: /Upload your resume/ });
    const input = container.querySelector("input[type=file]") as HTMLInputElement;
    const click = vi.spyOn(input, "click");

    await user.tab();
    expect(zone).toHaveFocus();

    await user.keyboard("{Enter}");
    expect(click).toHaveBeenCalled();
  });

  it("states the accepted formats and ceiling in its label", () => {
    render(<ResumeDropZone onFile={vi.fn()} onReject={vi.fn()} />);

    expect(screen.getByText("PDF, DOCX (Max 10MB)")).toBeInTheDocument();
    expect(screen.getByText("Drag & drop your resume here")).toBeInTheDocument();
    expect(screen.getByText("or click to browse")).toBeInTheDocument();
  });
});
