/** Route table per docs/15 §4. Every screen except global search (§6.8, still
 * a header dropdown TODO) is built. */

import { Navigate, Outlet, Route, Routes, useLocation } from "react-router-dom";
import type { ReactNode } from "react";
import { LoginPage } from "./auth/LoginPage";
import { useAuth } from "./auth/AuthContext";
import { CustomerProfilePage } from "./customers/CustomerProfilePage";
import { CustomersPage } from "./customers/CustomersPage";
import { DashboardPage } from "./dashboard/DashboardPage";
import { t } from "./i18n/bg";
import { IntakePage } from "./intake/IntakePage";
import { OrderPage } from "./order/OrderPage";
import { OrdersPage } from "./orders/OrdersPage";
import { PsPage } from "./ps/PsPage";
import { AppShell } from "./shell/AppShell";
import { RequireVendorAuth } from "./vendor/RequireVendorAuth";
import { VendorAuthProvider } from "./vendor/VendorAuthContext";
import { VendorCompaniesPage } from "./vendor/VendorCompaniesPage";
import { VendorCompanyDetailPage } from "./vendor/VendorCompanyDetailPage";
import { VendorLoginPage } from "./vendor/VendorLoginPage";
import { VendorShell } from "./vendor/VendorShell";

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
        <Route index element={<DashboardPage />} />
        <Route path="orders" element={<OrdersPage />} />
        <Route path="orders/new" element={<IntakePage />} />
        <Route path="orders/:id" element={<OrderPage />} />
        <Route path="customers" element={<CustomersPage />} />
        <Route path="customers/:id" element={<CustomerProfilePage />} />
        <Route path="ps" element={<PsPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>

      {/* Vendor Console (business-os/18, ADR-BOS-009): a structurally separate
          route tree, never linked from AppShell, never reachable from a
          tenant session. VendorAuthProvider wraps login too, mirroring how
          the tenant AuthProvider above covers /login as well. */}
      <Route path="/vendor" element={<VendorAuthProvider><Outlet /></VendorAuthProvider>}>
        <Route path="login" element={<VendorLoginPage />} />
        <Route
          element={
            <RequireVendorAuth>
              <VendorShell />
            </RequireVendorAuth>
          }
        >
          <Route index element={<Navigate to="companies" replace />} />
          <Route path="companies" element={<VendorCompaniesPage />} />
          <Route path="companies/:id" element={<VendorCompanyDetailPage />} />
          <Route path="*" element={<Navigate to="companies" replace />} />
        </Route>
      </Route>
    </Routes>
  );
}
