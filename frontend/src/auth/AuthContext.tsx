/**
 * Auth bootstrap (docs/15 §5.3): /auth/me drives everything. The provider owns
 * the CSRF token handoff to the api client and exposes the acting identity —
 * always visible in the shell (ADR-008).
 */

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createContext, useContext, useEffect, type ReactNode } from "react";
import { ApiError, api, setCsrfToken } from "../lib/api";
import { queryKeys } from "../lib/queryKeys";

export interface Me {
  user_id: string;
  name: string;
  email: string;
  is_owner: boolean;
  language: string;
  company_id: string;
  csrf_token: string;
  active_modules: string[];
  seat_limit: number | null;
  seat_usage: number;
}

interface AuthState {
  me: Me | null;
  isLoading: boolean;
  refresh: () => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: queryKeys.me,
    queryFn: () => api.get<Me>("/auth/me"),
    retry: (failureCount, error) =>
      !(error instanceof ApiError && error.status === 401) && failureCount < 2,
    staleTime: 5 * 60 * 1000,
  });

  useEffect(() => {
    setCsrfToken(data?.csrf_token ?? null);
  }, [data]);

  const refresh = async () => {
    await queryClient.invalidateQueries({ queryKey: queryKeys.me });
  };

  const logout = async () => {
    try {
      await api.post("/auth/logout");
    } finally {
      setCsrfToken(null);
      queryClient.clear();
    }
  };

  return (
    <AuthContext.Provider value={{ me: data ?? null, isLoading, refresh, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth outside AuthProvider");
  return ctx;
}
