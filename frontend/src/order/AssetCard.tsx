/** AssetCard (docs/15 §6.5): type + label + all typed field values, sourced
 * from GET /asset-types' field_defs (same mapping as the intake AssetStep). */

import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";
import { queryKeys } from "../lib/queryKeys";
import { t } from "../i18n/bg";
import { AssetTypeIcon } from "../intake/AssetTypeIcon";

interface FieldDef {
  key: string;
  label_bg: string;
  type: string;
  identifier_kind?: string;
}

interface AssetTypeOut {
  code: string;
  name_bg: string;
  field_defs: FieldDef[];
}

export function AssetCard({
  assetTypeCode,
  label,
  fieldValues,
}: {
  assetTypeCode: string;
  label: string;
  fieldValues: Record<string, unknown>;
}) {
  const { data: types } = useQuery({
    queryKey: queryKeys.assetTypes,
    queryFn: () => api.get<AssetTypeOut[]>("/asset-types"),
  });
  const type = types?.find((t2) => t2.code === assetTypeCode);

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-500">
        {t("order.asset")}
      </h3>
      <div className="mb-2 flex items-center gap-2">
        <AssetTypeIcon code={assetTypeCode} className="h-5 w-5 text-slate-400" />
        <span className="font-medium text-slate-800">{label}</span>
      </div>
      <dl className="grid grid-cols-2 gap-x-3 gap-y-1 text-sm">
        {(type?.field_defs ?? [])
          .filter((def) => fieldValues[def.key] !== undefined && fieldValues[def.key] !== "")
          .map((def) => (
            <div key={def.key} className="contents">
              <dt className="text-slate-500">{def.label_bg}</dt>
              <dd className="text-slate-800">{String(fieldValues[def.key])}</dd>
            </div>
          ))}
      </dl>
    </div>
  );
}
