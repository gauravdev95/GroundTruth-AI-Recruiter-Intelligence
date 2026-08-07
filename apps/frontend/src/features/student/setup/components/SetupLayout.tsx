import { Outlet } from "react-router-dom";

import { Backdrop } from "@/design/Surface";

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
 * The page background lives here rather than on each page for the same
 * reason: one background that never repaints between routes. That matters
 * more now than it did when this was a flat lavender tint — the `Backdrop`'s
 * blooms are fixed, and mounting them per route would restart three large
 * composited layers on every step of the wizard.
 */
export function SetupLayout() {
  return (
    <SetupUploadProvider>
      {/* `--bg` plus the shared ambient `Backdrop`, rather than the flat
          #F6F5FD this used to paint. Onboarding is the first authenticated
          surface a student sees, so it is the last place the product should
          look like a different application from the dashboard it leads to. */}
      <div className="relative min-h-screen bg-[var(--bg)]">
        <Backdrop />
        <SetupTopBar />
        <main className="mx-auto max-w-5xl px-4 pb-16 pt-6 sm:px-6 sm:pt-8">
          <Outlet />
        </main>
      </div>
    </SetupUploadProvider>
  );
}
