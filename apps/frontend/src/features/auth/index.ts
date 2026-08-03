export { authRoutes } from "./routes";
export { AuthProvider, useAuthContext } from "./context/AuthContext";
export { ProtectedRoute } from "./components/ProtectedRoute";
export { dashboardPathForRole } from "./lib/dashboardPath";
export type { AuthUser, UserRole } from "./api/authApi";
