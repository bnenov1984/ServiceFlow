/** CustomerCard (docs/15 §6.5): tel: click-to-call link (10 §6). */

import { Link } from "react-router-dom";
import { t } from "../i18n/bg";

export function CustomerCard({
  customerId,
  name,
  phone,
}: {
  customerId: string;
  name: string;
  phone: string;
}) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-500">
        {t("order.customer")}
      </h3>
      <Link to={`/customers/${customerId}`} className="font-medium text-blue-700 hover:underline">
        {name}
      </Link>
      <p>
        <a href={`tel:${phone}`} className="text-sm text-slate-500 hover:underline">
          {phone}
        </a>
      </p>
    </div>
  );
}
