// Bulgarian catalog — the only shipped language in V1 and the permanent fallback
// (ADR-015). Components never contain literal user-facing strings; they call t().
export const bg = {
  "app.name": "ServiceFlow",
  "health.checking": "Проверка на връзката…",
  "health.ok": "Системата работи нормално.",
  "health.degraded": "Системата работи с предупреждения.",
  "health.fail": "Има проблем със системата.",
  "health.unreachable": "Няма връзка със сървъра. Проверете дали компютърът на бюрото е включен.",
} as const;

export type MessageKey = keyof typeof bg;

export function t(key: MessageKey): string {
  return bg[key];
}
