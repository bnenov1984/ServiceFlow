/** Shared shapes for the orders board (docs/15 §6.3) — matches OrderListItemOut. */

export interface OrderListItem {
  id: string;
  number: string;
  customer_id: string;
  customer_name: string;
  asset_id: string;
  asset_label: string;
  complaint: string;
  status_code: string;
  status_kind: string;
  technician_id: string | null;
  priority: string;
  promised_on: string | null;
  warranty_days: number | null;
  origin_order_id: string | null;
  status_changed_at: string | null;
  overdue: boolean;
  archived: boolean;
}

export interface UserItem {
  id: string;
  name: string;
  is_owner: boolean;
  is_active: boolean;
}
