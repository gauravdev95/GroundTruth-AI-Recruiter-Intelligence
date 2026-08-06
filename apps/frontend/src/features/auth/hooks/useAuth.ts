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

/*
 * Both register hooks set the session on success, exactly as `useLogin` does.
 * Registration signs the new account in — there is no verification step
 * between creating the account and using it, so leaving the session unset
 * here would strand a signed-in user on a page that thinks they are anonymous.
 */
export function useCandidateRegister() {
  const { setSession } = useAuthContext();
  return useMutation({
    mutationFn: (payload: CandidateRegisterPayload) => authApi.registerCandidate(payload),
    onSuccess: (data) => setSession(data.user, data.access_token),
  });
}

export function useRecruiterRegister() {
  const { setSession } = useAuthContext();
  return useMutation({
    mutationFn: (payload: RecruiterRegisterPayload) => authApi.registerRecruiter(payload),
    onSuccess: (data) => setSession(data.user, data.access_token),
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
