/** Route table per docs/15 §4. Screens beyond the shell are stubs until their
 * FDD build slot (intake → order detail → kanban → dashboard/customers/search). */

import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import type { ReactNode } from "react";
import { LoginPage } from "./auth/LoginPage";
import { useAuth } from "./auth/AuthContext";
import { EmptyState } from "./components/States";
import { t } from "./i18n/bg";
import { IntakePage } from "./intake/IntakePage";
import { AppShell } from "./shell/AppShell";

function RequireAuth({ children }: { children: ReactNode }) {
  const { me, isLoading } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center text-slate-500">
        {t("common.loading")}
      </div>
    );
  }
  if (!me) {
    const next = encodeURIComponent(location.pathname + location.search);
    return <Navigate to={`/login?next=${next}`} replace />;
  }
  return <>{children}</>;
}

function StubScreen({ titleKey }: { titleKey: Parameters<typeof t>[0] }) {
  return (
    <div>
      <h1 className="mb-4 text-2xl font-bold text-slate-900">{t(titleKey)}</h1>
      <EmptyState text={t("shell.building")} />
    </div>
  );
}

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        element={
          <RequireAuth>
            <AppShell />
          </RequireAuth>
        }
      >
        <Route index element={<StubScreen titleKey="nav.dashboard" />} />
        <Route path="orders" element={<StubScreen titleKey="nav.orders" />} />
        <Route path="orders/new" element={<IntakePage />} />
        <Route path="orders/:id" element={<StubScreen titleKey="nav.orders" />} />
        <Route path="customers" element={<StubScreen titleKey="nav.customers" />} />
        <Route path="customers/:id" element={<StubScreen titleKey="nav.customers" />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
