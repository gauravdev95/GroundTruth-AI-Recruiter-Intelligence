import { apiClient } from "@/lib/apiClient";

export type UserRole = "candidate" | "recruiter" | "admin";

export interface AuthUser {
  id: string;
  email: string;
  full_name: string;
  role: UserRole;
  is_email_verified: boolean;
}

export interface AccessTokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: AuthUser;
}

export interface RegisterResponse {
  message: string;
  email: string;
  otp_expires_in_seconds: number;
}

export interface OtpExpiryResponse {
  message: string;
  otp_expires_in_seconds: number;
}

export interface GenericMessageResponse {
  message: string;
}

export interface CandidateRegisterPayload {
  full_name: string;
  email: string;
  phone_number: string;
  password: string;
  confirm_password: string;
  captcha_token: string;
  accept_terms: boolean;
}

export interface RecruiterRegisterPayload {
  full_name: string;
  company_name: string;
  company_email: string;
  password: string;
  confirm_password: string;
  captcha_token: string;
  accept_terms: boolean;
}

export interface LoginPayload {
  email: string;
  password: string;
  captcha_token: string;
  remember_me: boolean;
  expected_role: UserRole;
}

export const authApi = {
  registerCandidate: (payload: CandidateRegisterPayload) =>
    apiClient.post<RegisterResponse>("/auth/candidate/register", payload).then((res) => res.data),

  registerRecruiter: (payload: RecruiterRegisterPayload) =>
    apiClient.post<RegisterResponse>("/auth/recruiter/register", payload).then((res) => res.data),

  login: (payload: LoginPayload) =>
    apiClient.post<AccessTokenResponse>("/auth/login", payload).then((res) => res.data),

  logout: () => apiClient.post<GenericMessageResponse>("/auth/logout").then((res) => res.data),

  me: () => apiClient.get<AuthUser>("/auth/me").then((res) => res.data),

  verifyEmailConfirm: (email: string, otp: string) =>
    apiClient
      .post<GenericMessageResponse>("/auth/verify-email/confirm", { email, otp })
      .then((res) => res.data),

  verifyEmailResend: (email: string) =>
    apiClient.post<OtpExpiryResponse>("/auth/verify-email/resend", { email }).then((res) => res.data),

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
