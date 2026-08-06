import { screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { makeSetupState, renderWithProviders } from "@/test/renderWithProviders";

import { SetupUploadProvider } from "../hooks/useSetupUpload";
import { SetupResumePage } from "./SetupResumePage";

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>("react-router-dom");
  return { ...actual, useNavigate: () => vi.fn() };
});

const getState = vi.fn();
vi.mock("../api/setupApi", () => ({ setupApi: { getState: () => getState() } }));

const getJob = vi.fn();
const getDraftForUpload = vi.fn();
vi.mock("@/features/student/resume/api/resumeApi", async () => {
  const actual = await vi.importActual<typeof import("@/features/student/resume/api/resumeApi")>(
    "@/features/student/resume/api/resumeApi",
  );
  return {
    ...actual,
    resumeApi: {
      upload: vi.fn(),
      getJob: (id: string) => getJob(id),
      getDraftForUpload: (id: string) => getDraftForUpload(id),
      confirmDraft: vi.fn(),
      discardDraft: vi.fn(),
    },
  };
});

function renderPage() {
  return renderWithProviders(
    <SetupUploadProvider>
      <SetupResumePage />
    </SetupUploadProvider>,
    { route: "/student/profile/setup/resume" },
  );
}

describe("SetupResumePage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getJob.mockResolvedValue({ status: "running", attempts: 1, error: null });
    getDraftForUpload.mockRejectedValue(new Error("no draft"));
  });

  it("resumes into the analyzing state when the server says parsing", async () => {
    getState.mockResolvedValue(
      makeSetupState({
        resume: {
          has_upload: true,
          upload_id: "upload-1",
          status: "parsing",
          async_job_id: "job-1",
          draft_id: null,
          draft_status: null,
          original_filename: "ada.pdf",
          error: null,
        },
      }),
    );

    renderPage();

    expect(await screen.findByText("Analyzing your resume…")).toBeInTheDocument();
    expect(screen.getByRole("status")).toBeInTheDocument();
  });

  it("shows the failure reason and keeps the manual path reachable", async () => {
    getState.mockResolvedValue(
      makeSetupState({
        resume: {
          has_upload: true,
          upload_id: "upload-1",
          status: "failed",
          async_job_id: "job-1",
          draft_id: null,
          draft_status: null,
          original_filename: "scan.pdf",
          error: "NoTextContent: No readable text was found. Upload a text-based PDF.",
        },
      }),
    );

    renderPage();

    expect(await screen.findByText("We couldn't read that resume")).toBeInTheDocument();
    // The worker prefixes its message with the exception class; the student
    // only sees the sentence after it.
    expect(
      screen.getByText("No readable text was found. Upload a text-based PDF."),
    ).toBeInTheDocument();

    // Both exits present. The manual path must remain reachable from every
    // failure state.
    expect(screen.getByRole("button", { name: /Try again/ })).toBeInTheDocument();
    const manual = screen.getByRole("link", { name: /Fill manually instead/ });
    expect(manual).toHaveAttribute("href", "/student/profile/setup/manual");
  });

  it("offers the manual path when the job itself fails", async () => {
    getState.mockResolvedValue(
      makeSetupState({
        resume: {
          has_upload: true,
          upload_id: "upload-1",
          status: "uploaded",
          async_job_id: "job-1",
          draft_id: null,
          draft_status: null,
          original_filename: "ada.pdf",
          error: null,
        },
      }),
    );
    getJob.mockResolvedValue({
      status: "failed",
      attempts: 3,
      error: "This PDF is password protected.",
    });

    renderPage();

    expect(await screen.findByText("We couldn't read that resume")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Fill manually instead/ })).toBeInTheDocument();
  });

  it("always offers a switch to manual entry, even mid-analysis", async () => {
    getState.mockResolvedValue(
      makeSetupState({
        resume: {
          has_upload: true,
          upload_id: "upload-1",
          status: "parsing",
          async_job_id: "job-1",
          draft_id: null,
          draft_status: null,
          original_filename: "ada.pdf",
          error: null,
        },
      }),
    );

    renderPage();

    const link = await screen.findByRole("link", { name: "Switch to manual entry" });
    expect(link).toHaveAttribute("href", "/student/profile/setup/manual");
  });

  it("lands on the review screen for a parsed resume with an unconfirmed draft", async () => {
    getState.mockResolvedValue(
      makeSetupState({
        resume: {
          has_upload: true,
          upload_id: "upload-1",
          status: "parsed",
          async_job_id: "job-1",
          draft_id: "draft-1",
          draft_status: "pending_review",
          original_filename: "ada.pdf",
          error: null,
        },
      }),
    );
    getJob.mockResolvedValue({ status: "succeeded", attempts: 1, error: null });
    getDraftForUpload.mockResolvedValue({
      draft: {
        id: "draft-1",
        resume_upload_id: "upload-1",
        status: "pending_review",
        provider: "google",
        model: "gemini-3.6-flash",
        payload: {},
        confirmed_at: null,
        created_at: new Date().toISOString(),
      },
      suggestions: {
        basic: { headline: "Backend engineer" },
        technical: {},
        projects: [],
        certificates: [],
        experience: [],
        unmapped: [],
      },
    });

    renderPage();

    expect(await screen.findByText("Nothing here is saved yet.")).toBeInTheDocument();
  });
});
