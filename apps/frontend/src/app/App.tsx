import { QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Route, Routes } from "react-router-dom";

import { ToastProvider } from "@/components";
import { AuthProvider, authRoutes } from "@/features/auth";
import { LandingPage } from "@/features/landing";
import { recruiterRoutes } from "@/features/recruiter";
import { studentRoutes } from "@/features/student";
import { queryClient } from "@/lib/queryClient";

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <ToastProvider>
          <AuthProvider>
            <Routes>
              <Route path="/" element={<LandingPage />} />
              {authRoutes}
              {studentRoutes}
              {recruiterRoutes}
            </Routes>
          </AuthProvider>
        </ToastProvider>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;
