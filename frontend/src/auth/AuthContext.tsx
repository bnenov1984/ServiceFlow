/**
 * Auth bootstrap (docs/15 §5.3): /auth/me drives everything. The provider owns
 * the CSRF token handoff to the api client and exposes the acting identity —
 * always visible in the shell (ADR-008).
 */

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createContext, useContext, useEffect, type ReactNode } from "react";
import { ApiError, api, setCsrfToken } from "../lib/api";
import { queryKeys } from "../lib/queryKeys";
import { clearLastApp } from "../shell/lastApp";

export interface WarrantyDefaults {
  labor_days: number | null;
  parts_days: number | null;
}

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
  has_pin: boolean;
  // Optional on the TS shape (not on the wire — the backend always sends
  // it) so the many existing test fixtures that build a `Me` object by
  // hand don't all need updating for a field they don't exercise; real
  // consumers (DeliveryDialog, part-warranty prefill) read it defensively.
  warranty_defaults?: WarrantyDefaults;
  // Cleanup batch Issue 26: same "always on the wire, optional on the TS
  // shape" convention as warranty_defaults above — OrderStep reads this to
  // mark automotive mileage required client-side (the backend,
  // service_orders.service.create(), is the actual authority).
  business_profile?: string;
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
      // Reset "me" in place (data -> undefined) rather than removing the
      // query entirely: this hook's own useQuery observer stays subscribed
      // to the *same* query object throughout the component's lifetime
      // (AuthProvider never unmounts). queryClient.clear()/removeQueries
      // (everything, or "me" itself) destroys that object outright, and
      // when a subsequent login recreates a "me" query from scratch
      // (queryClient.setQueryData in LoginPage.tsx), this observer picked
      // it up unreliably - confirmed via a regression test that logs out
      // and immediately logs into a different company, which
      // intermittently kept reading the *previous* company's stale data.
      // (setQueryData(key, undefined) is a documented no-op in TanStack
      // Query - resetQueries is the supported way to clear in place.)
      queryClient.resetQueries({ queryKey: queryKeys.me });
      queryClient.removeQueries({ predicate: (q) => q.queryKey[0] !== "me" });
      clearLastApp();
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
