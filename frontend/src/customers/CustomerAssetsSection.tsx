/** AssetsSection (docs/15 §6.7): the customer's assets + "Нова поръчка за този
 * актив" — jumps into intake with customer/asset preselected. */

import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { AssetTypeIcon } from "../intake/AssetTypeIcon";
import { t } from "../i18n/bg";
import { api } from "../lib/api";
import { queryKeys } from "../lib/queryKeys";
import type { AssetItem } from "./types";

export function CustomerAssetsSection({
  customerId,
  customerName,
  customerPhone,
}: {
  customerId: string;
  customerName: string;
  customerPhone: string;
}) {
  const navigate = useNavigate();

  const { data: assets } = useQuery({
    queryKey: queryKeys.customerAssets(customerId),
    queryFn: () => api.get<AssetItem[]>(`/customers/${customerId}/assets`),
  });

  const startOrderFor = (asset: AssetItem) => {
    navigate("/orders/new", {
      state: {
        preselectedCustomer: { id: customerId, name: customerName, phone: customerPhone },
        preselectedAsset: { id: asset.id, label: asset.label, assetTypeCode: asset.asset_type_code },
      },
    });
  };

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-500">
        {t("customer.assets")}
      </h3>
      {assets && assets.length > 0 ? (
        <ul className="flex flex-col gap-2">
          {assets.filter((a) => !a.archived).map((asset) => (
            <li
              key={asset.id}
              className="flex items-center justify-between gap-3 rounded-lg border border-slate-100 px-3 py-2"
            >
              <div className="flex items-center gap-2">
                <AssetTypeIcon code={asset.asset_type_code} className="h-5 w-5 text-slate-400" />
                <span className="font-medium text-slate-800">{asset.label}</span>
              </div>
              <button
                type="button"
                onClick={() => startOrderFor(asset)}
                className="whitespace-nowrap text-sm font-medium text-blue-700 hover:underline min-h-touch"
              >
                {t("customer.new_order_for_asset")}
              </button>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-sm text-slate-400">{t("customer.assets_none")}</p>
      )}
    </div>
  );
}
