import { Outlet } from "react-router-dom";

import { SetupUploadProvider } from "../hooks/useSetupUpload";
import { SetupTopBar } from "./SetupTopBar";

/**
 * The chrome shared by every screen in the setup flow.
 *
 * A layout route so the top bar mounts once and survives navigation between
 * `/setup`, `/setup/resume` and `/setup/manual` — switching paths must not
 * flash the header, because a header that re-renders reads as a page reload
 * and a page reload reads as "did I just lose that?".
 *
 * The lavender page tint lives here rather than on each page for the same
 * reason: one background that never repaints between routes.
 */
export function SetupLayout() {
  return (
    <SetupUploadProvider>
      <div className="min-h-screen bg-[#F6F5FD]">
        <SetupTopBar />
        <main className="mx-auto max-w-5xl px-4 pb-16 pt-6 sm:px-6 sm:pt-8">
          <Outlet />
        </main>
      </div>
    </SetupUploadProvider>
  );
}
