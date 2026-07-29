import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";

import { onUnauthorized, refreshAccessToken } from "@/lib/apiClient";
import { setAccessToken } from "@/lib/tokenStore";

import { authApi, type AuthUser } from "../api/authApi";

interface AuthContextValue {
  user: AuthUser | null;
  /** True only while the initial silent-refresh-on-load check is in flight. */
  isLoading: boolean;
  setSession: (user: AuthUser, accessToken: string) => void;
  clearSession: () => void;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const setSession = useCallback((nextUser: AuthUser, token: string) => {
    setAccessToken(token);
    setUser(nextUser);
  }, []);

  const clearSession = useCallback(() => {
    setAccessToken(null);
    setUser(null);
  }, []);

  const logout = useCallback(async () => {
    try {
      await authApi.logout();
    } finally {
      clearSession();
    }
  }, [clearSession]);

  useEffect(() => {
    onUnauthorized(clearSession);
  }, [clearSession]);

  useEffect(() => {
    let cancelled = false;

    void (async () => {
      const token = await refreshAccessToken();
      if (cancelled) return;

      if (token) {
        try {
          const me = await authApi.me();
          if (!cancelled) setUser(me);
        } catch {
          clearSession();
        }
      }
      if (!cancelled) setIsLoading(false);
    })();

    return () => {
      cancelled = true;
    };
  }, [clearSession]);

  const value = useMemo(
    () => ({ user, isLoading, setSession, clearSession, logout }),
    [user, isLoading, setSession, clearSession, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuthContext(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuthContext must be used within an AuthProvider");
  }
  return ctx;
}
