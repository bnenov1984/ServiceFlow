/** Route table per docs/15 §4. Every screen except global search (§6.8, still
 * a header dropdown TODO) is built. */

import { Navigate, Route, Routes, useLocation } from "react-router-dom";
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
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
