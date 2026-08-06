import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { makeSetupState, renderWithProviders } from "@/test/renderWithProviders";

import { SetupUploadProvider } from "../hooks/useSetupUpload";
import { ProfileSetupPage } from "./ProfileSetupPage";

const navigate = vi.fn();

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>("react-router-dom");
  return { ...actual, useNavigate: () => navigate };
});

const getState = vi.fn();
vi.mock("../api/setupApi", () => ({ setupApi: { getState: () => getState() } }));

const chooseOnboarding = vi.fn().mockResolvedValue({});
const uploadResume = vi.fn();
vi.mock("@/features/student/api/profileApi", async () => {
  const actual = await vi.importActual<typeof import("@/features/student/api/profileApi")>(
    "@/features/student/api/profileApi",
  );
  return { ...actual, profileApi: { chooseOnboarding: () => chooseOnboarding() } };
});
vi.mock("@/features/student/resume/api/resumeApi", async () => {
  const actual = await vi.importActual<typeof import("@/features/student/resume/api/resumeApi")>(
    "@/features/student/resume/api/resumeApi",
  );
  return {
    ...actual,
    resumeApi: { upload: (file: File, onProgress?: (p: number) => void) => uploadResume(file, onProgress) },
  };
});

function renderPage() {
  return renderWithProviders(
    <SetupUploadProvider>
      <ProfileSetupPage />
    </SetupUploadProvider>,
    { route: "/student/profile/setup" },
  );
}

describe("ProfileSetupPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getState.mockResolvedValue(makeSetupState());
    uploadResume.mockResolvedValue({
      upload: { id: "upload-1" },
      async_job_id: "job-1",
    });
  });

  it("renders a skeleton rather than a wrong default while setup-state loads", async () => {
    let resolve: (value: unknown) => void = () => {};
    getState.mockReturnValue(new Promise((r) => (resolve = r)));

    renderPage();

    // No percentage at all — not "0%", which a returning student would read as
    // having lost their progress.
    expect(screen.queryByText(/% profile strength/)).not.toBeInTheDocument();
    expect(screen.queryByRole("list")).not.toBeInTheDocument();

    resolve(makeSetupState({ completion_percentage: 35, current_step_index: 1 }));
    expect(await screen.findByText("35% profile strength")).toBeInTheDocument();
  });

  it("renders the active step from setup-state", async () => {
    getState.mockResolvedValue(makeSetupState({ completion_percentage: 35, current_step_index: 2 }));

    renderPage();

    expect(await screen.findByText("35% profile strength")).toBeInTheDocument();
    // Scoped to the stepper's own list: the compact mobile indicator names the
    // active step too (jsdom renders both; only CSS hides one), and the option
    // cards contribute their own <ul>s to the page.
    const stepper = within(screen.getByRole("region", { name: "Profile setup progress" }));
    const active = within(stepper.getByRole("list"))
      .getByText("Connect GitHub")
      .closest("[aria-current]");
    expect(active).toHaveAttribute("aria-current", "step");
  });

  it("renders every element of the entry screen", async () => {
    renderPage();

    // Awaits a *data-gated* element first. The heading block renders
    // unconditionally, so waiting on it would proceed while the cards were
    // still skeletons.
    expect(await screen.findByText("0% profile strength")).toBeInTheDocument();
    expect(screen.getByText("Complete Your AI Verified Profile")).toBeInTheDocument();
    expect(
      screen.getByText(
        "Build your professional identity and increase your visibility to top recruiters.",
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Your data is secure and only visible to verified companies."),
    ).toBeInTheDocument();
    expect(screen.getByText("How would you like to create your profile?")).toBeInTheDocument();

    expect(screen.getByText("Recommended")).toBeInTheDocument();
    expect(screen.getByText("Upload Resume", { selector: "h3" })).toBeInTheDocument();
    expect(screen.getByText("AI-Powered Resume Parsing")).toBeInTheDocument();
    expect(screen.getByText("30 sec")).toBeInTheDocument();

    expect(screen.getByText("Fill Manually")).toBeInTheDocument();
    expect(screen.getByText("Why fill manually?")).toBeInTheDocument();
    expect(screen.getByText("Perfect for freshers & new graduates")).toBeInTheDocument();
    expect(screen.getByText("5–8 min")).toBeInTheDocument();

    expect(
      screen.getByText("You can switch between Resume Upload and Manual Entry at any time."),
    ).toBeInTheDocument();
    expect(screen.getByText("All your progress will be saved automatically.")).toBeInTheDocument();
  });

  it("routes to the manual path without waiting on the telemetry write", async () => {
    const user = userEvent.setup();
    // A failed bookkeeping write must not strand a student on this screen.
    chooseOnboarding.mockRejectedValue(new Error("nope"));

    renderPage();
    await user.click(await screen.findByRole("button", { name: "Start Manually" }));

    expect(navigate).toHaveBeenCalledWith("/student/profile/setup/manual");
  });

  it("starts the upload and routes to the resume path when a file is dropped", async () => {
    renderPage();
    await screen.findByText("Recommended");

    fireEvent.drop(screen.getByRole("button", { name: /Upload your resume/ }), {
      dataTransfer: { files: [new File(["x"], "ada.pdf", { type: "application/pdf" })] },
    });

    await waitFor(() => expect(uploadResume).toHaveBeenCalled());
    expect(navigate).toHaveBeenCalledWith("/student/profile/setup/resume");
  });

  it("shows a client-side rejection inline and uploads nothing", async () => {
    const { container } = renderPage();
    await screen.findByText("Recommended");

    // `change` is fired directly rather than via `user.upload`, which emulates
    // the browser's `accept` filter and would silently drop the file before
    // the component ever saw it — the rejection path is the thing under test.
    const input = container.querySelector("input[type=file]") as HTMLInputElement;
    Object.defineProperty(input, "files", {
      value: [new File(["x"], "notes.doc", { type: "application/msword" })],
      configurable: true,
    });
    fireEvent.change(input);

    expect(
      await screen.findByText("Legacy .doc isn't supported — save as PDF or DOCX"),
    ).toBeInTheDocument();
    expect(uploadResume).not.toHaveBeenCalled();
    expect(navigate).not.toHaveBeenCalled();
  });
});
