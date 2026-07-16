/** Shared shapes for the customers screens (docs/15 §6.7). */

export interface CustomerListItem {
  id: string;
  name: string;
  phone: string;
  phone2: string | null;
  email: string | null;
  archived: boolean;
  anonymized: boolean;
  active_orders_count: number;
}

export interface CustomerDetail {
  id: string;
  name: string;
  phone: string;
  phone2: string | null;
  email: string | null;
  archived: boolean;
  anonymized: boolean;
}

export interface AssetItem {
  id: string;
  asset_type_code: string;
  label: string;
  archived: boolean;
}
