/**
 * ReadySummary (Wave 2 Issue 8): once an order is "ready", it's operationally
 * frozen — no complaint/diagnosis edit buttons, no add-part/add-labor forms,
 * no part-state selector. Just a read-only recap: complaint, diagnosis, work
 * performed (labor), parts, and the total. Corrections go through the
 * existing workflow (move the order back to "repair" first, via
 * OrderHeader's status menu — unchanged by this component) rather than an
 * edit control living here. Reuses the same query keys/data ComplaintBlock/
 * DiagnosisCard/PartLinesSection/LaborLinesSection/MoneyCard already fetch —
 * no new endpoint, no stored-data change, this is presentation only.
 */

import { useQuery } from "@tanstack/react-query";
import { t } from "../i18n/bg";
import { api } from "../lib/api";
import { queryKeys } from "../lib/queryKeys";
import type { DiagnosisValue } from "./DiagnosisCard";

interface PartLineOut {
  id: string;
  name: string;
  qty: number;
  unit_price: number;
  state: string;
}

interface LaborLineOut {
  id: string;
  description: string;
  qty: number;
  unit_price: number;
}

function SummarySection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-500">
        {title}
      </h3>
      {children}
    </div>
  );
}

export function ReadySummary({
  orderId,
  complaint,
  diagnosis,
  estimatedTotal,
  paidAmount,
  balance,
}: {
  orderId: string;
  complaint: string;
  diagnosis: DiagnosisValue | null;
  estimatedTotal: number;
  paidAmount: number;
  balance: number;
}) {
  const { data: partLines } = useQuery({
    queryKey: queryKeys.orderPartLines(orderId),
    queryFn: () => api.get<PartLineOut[]>(`/orders/${orderId}/part-lines`),
  });
  const { data: laborLines } = useQuery({
    queryKey: queryKeys.orderLaborLines(orderId),
    queryFn: () => api.get<LaborLineOut[]>(`/orders/${orderId}/labor-lines`),
  });

  return (
    <div className="flex flex-col gap-4">
      <SummarySection title={t("order.complaint")}>
        <p className="whitespace-pre-wrap text-slate-700">{complaint}</p>
      </SummarySection>

      <SummarySection title={t("order.diagnosis")}>
        {diagnosis ? (
          <dl className="flex flex-col gap-2 text-sm text-slate-700">
            {diagnosis.observed && (
              <div>
                <dt className="text-xs font-medium uppercase tracking-wide text-slate-500">{t("order.diagnosis_observed")}</dt>
                <dd className="mt-0.5">{diagnosis.observed}</dd>
              </div>
            )}
            {diagnosis.cause && (
              <div>
                <dt className="text-xs font-medium uppercase tracking-wide text-slate-500">{t("order.diagnosis_cause")}</dt>
                <dd className="mt-0.5">{diagnosis.cause}</dd>
              </div>
            )}
            {diagnosis.recommendation && (
              <div>
                <dt className="text-xs font-medium uppercase tracking-wide text-slate-500">{t("order.diagnosis_recommendation")}</dt>
                <dd className="mt-0.5">{diagnosis.recommendation}</dd>
              </div>
            )}
          </dl>
        ) : (
          <p className="text-sm text-slate-400">{t("order.diagnosis_none")}</p>
        )}
      </SummarySection>

      <SummarySection title={t("order.labor_lines")}>
        <ul className="flex flex-col gap-1">
          {(laborLines ?? []).map((line) => (
            <li key={line.id} className="text-sm text-slate-700">
              {line.description} · {line.unit_price.toFixed(2)} €
            </li>
          ))}
          {laborLines?.length === 0 && <p className="text-sm text-slate-400">{t("order.labor_lines_none")}</p>}
        </ul>
      </SummarySection>

      <SummarySection title={t("order.part_lines")}>
        <ul className="flex flex-col gap-1">
          {(partLines ?? []).map((line) => (
            <li key={line.id} className="text-sm text-slate-700">
              {line.name} · {line.unit_price.toFixed(2)} €
            </li>
          ))}
          {partLines?.length === 0 && <p className="text-sm text-slate-400">{t("order.part_lines_none")}</p>}
        </ul>
      </SummarySection>

      <SummarySection title={t("order.money")}>
        <p className="text-2xl font-bold tabular-nums text-slate-900">{estimatedTotal.toFixed(2)} €</p>
        <dl className="mt-2 flex flex-col gap-1 text-sm">
          <div className="flex justify-between">
            <dt className="text-slate-500">{t("order.money_paid")}</dt>
            <dd className="tabular-nums text-slate-900">{paidAmount.toFixed(2)} €</dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-slate-500">{t("order.money_balance")}</dt>
            <dd className="tabular-nums text-slate-900">{balance.toFixed(2)} €</dd>
          </div>
        </dl>
      </SummarySection>
    </div>
  );
}
