/** Vendor Console route guard — mirrors App.tsx's tenant `RequireAuth`, kept
 * in its own file (unlike the tenant guard) so it is directly unit-testable. */

import { Navigate, useLocation } from "react-router-dom";
import type { ReactNode } from "react";
import { t } from "../i18n/bg";
import { useVendorAuth } from "./VendorAuthContext";

export function RequireVendorAuth({ children }: { children: ReactNode }) {
  const { me, isLoading } = useVendorAuth();
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
    return <Navigate to={`/vendor/login?next=${next}`} replace />;
  }
  return <>{children}</>;
}
