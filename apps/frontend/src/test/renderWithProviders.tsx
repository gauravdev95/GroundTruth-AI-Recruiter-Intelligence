import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, type RenderOptions } from "@testing-library/react";
import type { ReactElement, ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";

import { ToastProvider } from "@/components/Toast";
import type { SetupState, SetupStep } from "@/features/student/setup/api/setupApi";

/**
 * Test-only query client.
 *
 * Retries are off so a deliberately failing request surfaces as an error state
 * immediately instead of after three backoffs, and caching is off so one
 * test's fixture cannot leak into the next.
 */
export function makeTestQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0, staleTime: 0 },
      mutations: { retry: false },
    },
  });
}

interface ProviderOptions extends Omit<RenderOptions, "wrapper"> {
  route?: string;
  queryClient?: QueryClient;
}

export function renderWithProviders(
  ui: ReactElement,
  { route = "/", queryClient = makeTestQueryClient(), ...options }: ProviderOptions = {},
) {
  function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={[route]}>
          <ToastProvider>{children}</ToastProvider>
        </MemoryRouter>
      </QueryClientProvider>
    );
  }

  return { queryClient, ...render(ui, { wrapper: Wrapper, ...options }) };
}

/** Mirrors `setup_state.SETUP_STEPS`, including the two steps that are not
 * profile sections — a fixture missing `choose`/`review` would let a test pass
 * against a seven-step UI while describing a five-step server. */
const STEP_META: { key: SetupStep["key"]; title: string; subtitle: string; mandatory: boolean }[] = [
  { key: "choose", title: "Get Started", subtitle: "Upload a resume or fill it in yourself", mandatory: true },
  { key: "basic", title: "Basic Information", subtitle: "Personal details & education", mandatory: true },
  {
    key: "github",
    title: "Connect GitHub",
    subtitle: "Read-only access to your public repositories",
    mandatory: true,
  },
  { key: "projects", title: "Link Projects", subtitle: "Choose up to three repositories", mandatory: true },
  { key: "coding", title: "Coding Profile", subtitle: "Optional — a supporting signal", mandatory: false },
  {
    key: "certificates",
    title: "Certificates",
    subtitle: "Optional — issuer-verified credentials",
    mandatory: false,
  },
  {
    key: "experience",
    title: "Experience",
    subtitle: "Optional — internships & jobs",
    mandatory: false,
  },
  { key: "review", title: "Review & Submit", subtitle: "Check everything, then submit", mandatory: true },
];

/** Builds a `setup-state` payload shaped exactly like the server's, so a test
 * cannot pass against a shape the API does not actually return. */
export function makeSetupState(overrides: Partial<SetupState> = {}): SetupState {
  const currentStepIndex = overrides.current_step_index ?? 0;
  const statuses = overrides.steps?.map((step) => step.status);

  return {
    completion_percentage: 0,
    current_step_index: currentStepIndex,
    meets_section_requirements: false,
    is_discoverable: false,
    is_submitted: false,
    can_submit: false,
    blocking: [],
    resume: {
      has_upload: false,
      upload_id: null,
      status: null,
      async_job_id: null,
      draft_id: null,
      draft_status: null,
      original_filename: null,
      error: null,
    },
    ...overrides,
    steps:
      overrides.steps ??
      STEP_META.map((meta, index) => ({
        key: meta.key,
        index,
        title: meta.title,
        subtitle: meta.subtitle,
        status: statuses?.[index] ?? "empty",
        is_mandatory: meta.mandatory,
        is_current: index === currentStepIndex,
        filled_count: 0,
        required_count:
          meta.key === "basic" ? 7 : meta.key === "github" || meta.key === "projects" ? 1 : 0,
      })),
  };
}
