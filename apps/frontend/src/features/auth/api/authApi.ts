import { apiClient } from "@/lib/apiClient";

export type UserRole = "candidate" | "recruiter" | "admin";

export interface AuthUser {
  id: string;
  email: string;
  /** Null for a student between signup and their first onboarding section save
   * — `User.full_name` on the backend is nullable and this mirrors it. Was
   * typed `string` here, which was a lie the compiler then propagated into
   * every consumer; anything rendering a name must handle the null. */
  full_name: string | null;
  role: UserRole;
}

export interface AccessTokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: AuthUser;
}

export interface GenericMessageResponse {
  message: string;
}

/**
 * Student signup is two fields. Name and phone are collected in the first
 * onboarding section instead — see `CandidateRegisterRequest` on the backend
 * for the reasoning, and `BasicInfoRequest` for where they went.
 */
export interface CandidateRegisterPayload {
  email: string;
  password: string;
  /** Optional: the widget only mounts when a site key is configured. */
  captcha_token?: string;
}

export interface RecruiterRegisterPayload {
  full_name: string;
  company_name: string;
  company_email: string;
  password: string;
  confirm_password: string;
  accept_terms: boolean;
}

export interface LoginPayload {
  email: string;
  password: string;
  remember_me: boolean;
  /** Optional, and the unified `/login` page omits it: the role comes back on
   * the issued session rather than being asserted up front. The server still
   * enforces it when present, for any caller that does know the lane. */
  expected_role?: UserRole;
}

export const authApi = {
  /*
   * Both register calls return an `AccessTokenResponse`, exactly like `login`.
   * There is no email-verification step: the account is created, signed in and
   * usable in one request, so the caller navigates straight to the dashboard
   * instead of to a code-entry screen.
   */
  registerCandidate: (payload: CandidateRegisterPayload) =>
    apiClient.post<AccessTokenResponse>("/auth/candidate/register", payload).then((res) => res.data),

  registerRecruiter: (payload: RecruiterRegisterPayload) =>
    apiClient.post<AccessTokenResponse>("/auth/recruiter/register", payload).then((res) => res.data),

  login: (payload: LoginPayload) =>
    apiClient.post<AccessTokenResponse>("/auth/login", payload).then((res) => res.data),

  logout: () => apiClient.post<GenericMessageResponse>("/auth/logout").then((res) => res.data),

  me: () => apiClient.get<AuthUser>("/auth/me").then((res) => res.data),

  forgotPassword: (email: string) =>
    apiClient.post<GenericMessageResponse>("/auth/forgot-password", { email }).then((res) => res.data),

  resetPassword: (token: string, newPassword: string, confirmPassword: string) =>
    apiClient
      .post<GenericMessageResponse>("/auth/reset-password", {
        token,
        new_password: newPassword,
        confirm_password: confirmPassword,
      })
      .then((res) => res.data),

  googleLoginUrl: (role: UserRole) =>
    `${import.meta.env.VITE_API_BASE_URL}/auth/google/login?role=${role}`,
};
