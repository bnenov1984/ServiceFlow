/** Shared Invoice view-model types (docs/01 §Invoice) — the response shapes
 * `IssuedInvoiceView`/`InvoiceDraftEditor` render, reused by both the
 * order-centric `InvoiceCard` and the invoice-centric `InvoiceDetailPage`. */

export interface InvoiceOut {
  id: string;
  // Wave 6 Issue 30 — exactly one of order_id/customer_id is ever set (a
  // manual invoice has no ServiceOrder; an order-generated one resolves its
  // buyer through the order instead of customer_id).
  order_id: string | null;
  customer_id: string | null;
  status: string;
  number: number | null;
  currency: string;
  row_version: number;
}

export interface InvoiceLineOut {
  id: string;
  description: string;
  qty: number;
  unit_price: number;
  vat_rate: number | null;
  source: string;
}

export interface SellerSnapshot {
  name: string;
  address: string;
  eik: string;
  vat_registered: boolean;
  vat_number?: string;
}

export interface BuyerSnapshot {
  name: string;
  address?: string;
  eik?: string;
  vat_registered?: boolean;
  vat_number?: string;
}

export interface InvoiceDetailOut extends InvoiceOut {
  lines: InvoiceLineOut[];
  draft_total: number;
  tax_event_date: string | null;
  issued_at: string | null;
  seller: SellerSnapshot | null;
  buyer: BuyerSnapshot | null;
  vat_mode: string | null;
  net: number | null;
  vat: number | null;
  gross: number | null;
  // Wave 6 Issue 30 — both null unless annul() has transitioned this
  // invoice to "annulled"; the frozen fields above are never touched.
  annulled_at: string | null;
  annul_reason: string | null;
}
