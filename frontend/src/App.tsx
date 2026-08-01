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
import { EmployeesPage } from "./settings/EmployeesPage";
import { AppChooserPage, NoActiveAppsPage } from "./shell/AppChooser";
import { AppShell } from "./shell/AppShell";
import { getLastApp } from "./shell/lastApp";
import { RequireVendorAuth } from "./vendor/RequireVendorAuth";
import { VendorAuthProvider } from "./vendor/VendorAuthContext";
import { VendorCompaniesPage } from "./vendor/VendorCompaniesPage";
import { VendorCompanyDetailPage } from "./vendor/VendorCompanyDetailPage";
import { VendorLoginPage } from "./vendor/VendorLoginPage";
import { VendorNewCompanyPage } from "./vendor/VendorNewCompanyPage";
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

/** "/" is RepairFlow's own dashboard route — never the default just because
 * it's first in the list (PO decision, 01.08.2026: no application is active
 * by default, and RepairFlow is not privileged over PropertyFlow). The
 * landing page is derived entirely from the authenticated company's
 * active_modules:
 * - RepairFlow only -> this route's own <DashboardPage />
 * - PropertyFlow only -> redirect to "/ps"
 * - both -> the remembered last-used app (lastApp.ts), or the chooser if
 *   there's no preference yet - never silently RepairFlow
 * - neither -> a neutral "no applications enabled" state, not an error
 * `AppShell`'s own `currentApp` fallback is a second line of defense for
 * deep links that land past this point (e.g. "/settings/employees" for a
 * company with zero active apps). */
function IndexRoute() {
  const { me } = useAuth();
  if (!me) return null; // unreachable: RequireAuth already gates on `me`

  const hasRepairFlow = me.active_modules.includes("repairflow");
  const hasPropertyFlow = me.active_modules.includes("professional-services");

  if (hasRepairFlow && hasPropertyFlow) {
    const last = getLastApp();
    if (last === "propertyflow") return <Navigate to="/ps" replace />;
    if (last === "repairflow") return <DashboardPage />;
    return <Navigate to="/choose-app" replace />;
  }
  if (hasPropertyFlow) return <Navigate to="/ps" replace />;
  if (hasRepairFlow) return <DashboardPage />;
  return <Navigate to="/no-apps" replace />;
}

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      {/* Standalone, outside AppShell - neither state has a single "current
          app" to build per-app nav/toolbar chrome around. */}
      <Route path="/choose-app" element={<RequireAuth><AppChooserPage /></RequireAuth>} />
      <Route path="/no-apps" element={<RequireAuth><NoActiveAppsPage /></RequireAuth>} />
      <Route
        element={
          <RequireAuth>
            <AppShell />
          </RequireAuth>
        }
      >
        <Route index element={<IndexRoute />} />
        <Route path="orders" element={<OrdersPage />} />
        <Route path="orders/new" element={<IntakePage />} />
        <Route path="orders/:id" element={<OrderPage />} />
        <Route path="customers" element={<CustomersPage />} />
        <Route path="customers/:id" element={<CustomerProfilePage />} />
        <Route path="ps" element={<PsPage />} />
        <Route path="settings/employees" element={<EmployeesPage />} />
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
          <Route path="companies/new" element={<VendorNewCompanyPage />} />
          <Route path="companies/:id" element={<VendorCompanyDetailPage />} />
          <Route path="*" element={<Navigate to="companies" replace />} />
        </Route>
      </Route>
    </Routes>
  );
}
