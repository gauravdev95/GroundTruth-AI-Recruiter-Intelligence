import { Suspense, useEffect } from "react";
import { QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Route, Routes, useLocation } from "react-router-dom";

// Imported from the module, not the barrel: `@/components/index.ts` re-exports
// eleven components, and pulling one through it drags a shared chunk containing
// the dashboard shell, modal, card and select — none of which the landing route
// renders — onto the critical path.
import { ToastProvider } from "@/components/Toast";
import { AuthProvider, authRoutes } from "@/features/auth";
import { LandingPage } from "@/features/landing";
import { legalRoutes } from "@/features/legal";
import { recruiterRoutes } from "@/features/recruiter";
import { studentRoutes } from "@/features/student";
import { queryClient } from "@/lib/queryClient";

/**
 * React Router keeps the window's scroll position across navigations, so
 * leaving the landing page half-scrolled used to drop you into the middle of
 * the next page. `behavior: "instant"` is required: the landing stylesheet sets
 * `scroll-behavior: smooth` on <html>, which would otherwise animate the reset.
 */
function ScrollToTop() {
  const { pathname } = useLocation();

  useEffect(() => {
    window.scrollTo({ top: 0, left: 0, behavior: "instant" });
  }, [pathname]);

  return null;
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <ScrollToTop />
        <ToastProvider>
          <AuthProvider>
            {/*
              One boundary covering every lazy route. The auth pages and both
              dashboards are code-split; the landing page deliberately is not.
              Splitting the LCP route would only move its code behind a second
              request — the saving comes from the routes a first-time visitor
              never opens, which is all of the others.
            */}
            <Suspense fallback={
              <div className="flex h-screen items-center justify-center bg-gt-vault">
                <div className="h-8 w-8 animate-spin rounded-full border-2 border-white/20 border-t-gt-electric" />
              </div>
            }>
              <Routes>
                <Route path="/" element={<LandingPage />} />
                {legalRoutes}
                {authRoutes}
                {studentRoutes}
                {recruiterRoutes}
              </Routes>
            </Suspense>
          </AuthProvider>
        </ToastProvider>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;
