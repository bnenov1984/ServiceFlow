/** StatWidget (docs/15 §6.2): a big number, a label, and a link into a filtered
 * orders view. Highlight is an optional secondary line (e.g. Готови над N дни). */

import { Link } from "react-router-dom";

export function StatWidget({
  to,
  label,
  value,
  highlight,
}: {
  to: string;
  label: string;
  value: number;
  highlight?: string;
}) {
  return (
    <Link
      to={to}
      className="flex flex-col gap-1 rounded-lg border border-slate-200 bg-white p-4 shadow-sm hover:border-blue-300 hover:shadow-md min-h-touch"
    >
      <span className="text-sm font-medium text-slate-500">{label}</span>
      <span className="text-3xl font-bold text-slate-900">{value}</span>
      {highlight && <span className="text-xs font-medium text-red-600">{highlight}</span>}
    </Link>
  );
}
