/**
 * Vendor Console auth (business-os/18 §9, ADR-BOS-009): structurally separate
 * from the tenant `AuthContext` — its own context, its own query key, its own
 * `/platform-admin/*` endpoints, its own CSRF slot (`lib/api.ts`). Mirrors
 * `auth/AuthContext.tsx`'s shape deliberately, but is not a variant of it —
 * ADR-BOS-009 rejects a shared session type on the backend, and the same
 * reasoning holds here.
 */

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createContext, useContext, useEffect, type ReactNode } from "react";
import { ApiError, api, setVendorCsrfToken } from "../lib/api";
import { queryKeys } from "../lib/queryKeys";
import type { VendorMe } from "./types";

interface VendorAuthState {
  me: VendorMe | null;
  isLoading: boolean;
  refresh: () => Promise<void>;
  logout: () => Promise<void>;
}

const VendorAuthContext = createContext<VendorAuthState | null>(null);

export function VendorAuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: queryKeys.vendorMe,
    queryFn: () => api.get<VendorMe>("/platform-admin/me"),
    retry: (failureCount, error) =>
      !(error instanceof ApiError && error.status === 401) && failureCount < 2,
    staleTime: 5 * 60 * 1000,
  });

  useEffect(() => {
    setVendorCsrfToken(data?.csrf_token ?? null);
  }, [data]);

  const refresh = async () => {
    await queryClient.invalidateQueries({ queryKey: queryKeys.vendorMe });
  };

  const logout = async () => {
    try {
      await api.post("/platform-admin/auth/logout");
    } finally {
      setVendorCsrfToken(null);
      // Scoped, not queryClient.clear(): a tenant session can be alive in the
      // same tab (client-side routing between /vendor/* and the tenant app
      // never reloads the page) — vendor logout must not wipe its cache.
      // vendorMe itself is reset in place, not removed: this hook's own
      // useQuery observer stays subscribed to the *same* query object for
      // the component's whole lifetime, and removing it outright orphans
      // that subscription for whatever a subsequent login recreates - see
      // auth/AuthContext.tsx's identical fix for the confirmed regression.
      // (setQueryData(key, undefined) is a documented no-op in TanStack
      // Query - resetQueries is the supported way to clear in place.)
      queryClient.resetQueries({ queryKey: queryKeys.vendorMe });
      queryClient.removeQueries({
        predicate: (q) => q.queryKey[0] === "vendor" && q.queryKey[1] !== "me",
      });
    }
  };

  return (
    <VendorAuthContext.Provider value={{ me: data ?? null, isLoading, refresh, logout }}>
      {children}
    </VendorAuthContext.Provider>
  );
}

export function useVendorAuth(): VendorAuthState {
  const ctx = useContext(VendorAuthContext);
  if (!ctx) throw new Error("useVendorAuth outside VendorAuthProvider");
  return ctx;
}
