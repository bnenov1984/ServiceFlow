/** Shared shapes for the customers screens (docs/15 §6.7). */

export interface CustomerCompanyRequisites {
  address: string | null;
  eik: string | null;
  vat_number: string | null;
}

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
  is_company: boolean;
  vat_registered: boolean | null;
  company_requisites: CustomerCompanyRequisites | null;
  archived: boolean;
  anonymized: boolean;
}

export interface AssetItem {
  id: string;
  asset_type_code: string;
  label: string;
  archived: boolean;
}
