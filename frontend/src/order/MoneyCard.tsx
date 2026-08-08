/** MoneyCard (docs/15 §6.5): parts+labor computed total (the same
 * lines.order_totals the backend derives paid_amount/balance from — docs/01
 * §Payment, BR-3). Invoice actions live in InvoiceCard, not here — this card
 * is payments/totals only (Phase-A Invoice Issue moved the one real Issue
 * action there). */

import { t } from "../i18n/bg";

export function MoneyCard({
  estimatedTotal,
  paidAmount,
  balance,
}: {
  estimatedTotal: number;
  paidAmount: number;
  balance: number;
}) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-500">
        {t("order.money")}
      </h3>
      <p className="text-2xl font-bold tabular-nums text-slate-900">
        {estimatedTotal.toFixed(2)} €
      </p>
      <p className="mb-3 text-xs text-slate-400">{t("order.money_hint")}</p>
      <dl className="mb-3 flex flex-col gap-1 text-sm">
        <div className="flex justify-between">
          <dt className="text-slate-500">{t("order.money_paid")}</dt>
          <dd className="tabular-nums text-slate-900">{paidAmount.toFixed(2)} €</dd>
        </div>
        <div className="flex justify-between">
          <dt className="text-slate-500">{t("order.money_balance")}</dt>
          <dd className="tabular-nums text-slate-900">{balance.toFixed(2)} €</dd>
        </div>
      </dl>
    </div>
  );
}
