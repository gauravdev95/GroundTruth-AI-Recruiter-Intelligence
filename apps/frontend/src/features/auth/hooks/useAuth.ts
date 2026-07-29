import { useMutation } from "@tanstack/react-query";

import {
  authApi,
  type CandidateRegisterPayload,
  type LoginPayload,
  type RecruiterRegisterPayload,
} from "../api/authApi";
import { useAuthContext } from "../context/AuthContext";

export function useLogin() {
  const { setSession } = useAuthContext();
  return useMutation({
    mutationFn: (payload: LoginPayload) => authApi.login(payload),
    onSuccess: (data) => setSession(data.user, data.access_token),
  });
}

export function useCandidateRegister() {
  return useMutation({
    mutationFn: (payload: CandidateRegisterPayload) => authApi.registerCandidate(payload),
  });
}

export function useRecruiterRegister() {
  return useMutation({
    mutationFn: (payload: RecruiterRegisterPayload) => authApi.registerRecruiter(payload),
  });
}

export function useVerifyEmail() {
  return useMutation({
    mutationFn: ({ email, otp }: { email: string; otp: string }) => authApi.verifyEmailConfirm(email, otp),
  });
}

export function useResendOtp() {
  return useMutation({
    mutationFn: (email: string) => authApi.verifyEmailResend(email),
  });
}

export function useForgotPassword() {
  return useMutation({
    mutationFn: (email: string) => authApi.forgotPassword(email),
  });
}

export function useResetPassword() {
  return useMutation({
    mutationFn: ({
      token,
      newPassword,
      confirmPassword,
    }: {
      token: string;
      newPassword: string;
      confirmPassword: string;
    }) => authApi.resetPassword(token, newPassword, confirmPassword),
  });
}

export function useLogout() {
  const { logout } = useAuthContext();
  return useMutation({ mutationFn: logout });
}
