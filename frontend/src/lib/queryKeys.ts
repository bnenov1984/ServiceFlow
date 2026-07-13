/** Query-keys registry (docs/15 §5.2) — никакви ad-hoc ключове извън този файл. */

export const queryKeys = {
  me: ["me"] as const,
  health: ["health"] as const,
  dashboard: ["dashboard"] as const,
  users: ["users"] as const,
  assetTypes: ["asset-types"] as const,
  orders: (filters?: Record<string, string>) => ["orders", filters ?? {}] as const,
  order: (id: string) => ["order", id] as const,
  orderTimeline: (id: string) => ["order", id, "timeline"] as const,
  customers: (q?: string) => ["customers", q ?? ""] as const,
  customer: (id: string) => ["customer", id] as const,
  customerAssets: (id: string) => ["customer", id, "assets"] as const,
  search: (q: string) => ["search", q] as const,
};
