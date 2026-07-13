// Bulgarian catalog — the only shipped language in V1 and the permanent fallback
// (ADR-015). Components never contain literal user-facing strings; they call t().
// Params use {name} placeholders. Backend message_key values (docs/09 §1) live
// here too — the API never returns prose, the catalog renders it.

export const bg = {
  "app.name": "ServiceFlow",

  // --- shell ---
  "nav.dashboard": "Табло",
  "nav.orders": "Поръчки",
  "nav.customers": "Клиенти",
  "nav.invoices": "Фактури",
  "nav.settings": "Настройки",
  "nav.coming_soon": "Очаквайте скоро",
  "shell.new_order": "+ Нова поръчка",
  "shell.search_placeholder": "Търсене: клиент, телефон, №, IMEI…",
  "shell.logout": "Изход",
  "shell.switch_user": "Смяна на потребител",
  "shell.locked_title": "Екранът е заключен",
  "shell.locked_hint": "Изберете потребител и въведете PIN, за да продължите.",
  "shell.building": "Този екран се изгражда.",
  "shell.you_suffix": "{name} (вие)",

  // --- health (docs/10 §1: one banner, plain sentence + next step) ---
  "health.checking": "Проверка на връзката…",
  "health.ok": "Системата работи нормално.",
  "health.degraded": "Системата работи с предупреждения.",
  "health.fail": "Има проблем със системата.",
  "health.unreachable": "Няма връзка със сървъра. Проверете интернет връзката и опитайте отново.",

  // --- auth ---
  "auth.title": "Вход",
  "auth.email": "Имейл",
  "auth.password": "Парола",
  "auth.submit": "Влез",
  "auth.pin_title": "Смяна на потребител",
  "auth.pin_hint": "Изберете потребител и въведете PIN.",
  "auth.pin_clear": "Изтрий",
  "auth.pin_confirm": "Потвърди",

  // --- search dropdown ---
  "search.customers": "Клиенти",
  "search.orders": "Поръчки",
  "search.assets": "Активи",
  "search.empty": "Нищо не е намерено за „{q}“.",

  // --- common ---
  "common.retry": "Опитай отново",
  "common.cancel": "Отказ",
  "common.save": "Запази",
  "common.close": "Затвори",
  "common.loading": "Зареждане…",

  // --- backend message keys (docs/09 §1 contract) ---
  "errors.internal": "Възникна неочаквана грешка. Опитайте отново.",
  "errors.validation": "Някои полета не са попълнени коректно.",
  "errors.db_not_configured": "Системата не е свързана с база данни.",
  "errors.auth.required": "Необходимо е да влезете в системата.",
  "errors.auth.invalid_credentials": "Грешен имейл или парола.",
  "errors.auth.locked_out": "Твърде много опити. Изчакайте 15 минути и опитайте отново.",
  "errors.auth.session_expired": "Сесията е изтекла. Влезте отново.",
  "errors.auth.csrf": "Заявката е отхвърлена от защитата. Презаредете страницата.",
  "errors.auth.owner_required": "Само собственикът може да направи това.",
  "errors.auth.invalid_pin": "Грешен PIN.",
  "errors.customers.not_found": "Няма такъв клиент.",
  "errors.customers.anonymized": "Клиентът е анонимизиран и не може да се редактира.",
  "errors.assets.not_found": "Няма такъв актив.",
  "errors.assets.unknown_type": "Непознат тип актив.",
  "errors.assets.invalid_fields": "Някои полета на актива не са коректни.",
  "errors.orders.not_found": "Няма такава поръчка.",
  "errors.orders.asset_mismatch": "Активът не принадлежи на този клиент.",
  "errors.orders.invalid_transition": "Този преход на статус не е позволен.",
  "errors.orders.reason_required": "Необходима е причина.",
  "errors.orders.approval_required": "Необходимо е записано одобрение от клиента.",
  "errors.orders.archived": "Поръчката е архивирана.",
  "errors.orders.not_terminal": "Поръчката не е приключена.",
  "errors.orders.terminal_readonly": "Приключена поръчка не може да се редактира.",
  "errors.orders.unlock_window_expired": "Срокът за отключване (24 ч) е изтекъл.",
  "errors.orders.warranty_needs_delivered": "Гаранционно връщане е възможно само за предадена поръчка.",
  "errors.tasks.not_found": "Няма такава задача.",
  "errors.tasks.order_terminal": "Поръчката е приключена — задачите са заключени.",
  "errors.part_lines.not_found": "Няма такъв ред за част.",
  "errors.part_lines.invalid_state": "Невалидно състояние на частта.",
  "errors.labor_lines.not_found": "Няма такъв ред за труд.",
  "errors.accessories.not_found": "Няма такъв аксесоар.",
  "errors.attachments.not_found": "Няма такъв файл.",
  "errors.attachments.invalid_stage": "Невалиден етап на снимката.",
  "errors.attachments.too_large": "Файлът е твърде голям (максимум 10 MB).",
  "errors.attachments.too_many": "Достигнат е лимитът файлове за тази поръчка.",
  "errors.attachments.unsupported_type": "Неподдържан тип файл. Позволени: снимки и PDF.",
  "errors.contacts.not_found": "Няма такъв запис.",
  "errors.contacts.invalid_type": "Невалиден тип комуникация.",
  "errors.contacts.direction_required": "Посочете входящо или изходящо.",
  "errors.contacts.not_author": "Само авторът може да редактира записа.",
  "errors.contacts.frozen": "Записът вече не може да се редактира.",
  "errors.protocol.delivery_not_available": "Протоколът за предаване очаквайте в следваща версия.",
  "errors.protocol.invalid_type": "Невалиден тип протокол.",
} as const;

export type MessageKey = keyof typeof bg;

export function t(key: MessageKey | string, params?: Record<string, string | number>): string {
  // Unknown keys (e.g. a backend key added before the catalog) fall back to the
  // generic error text rather than leaking raw keys to users (docs/15 §5.1).
  const template =
    key in bg ? bg[key as MessageKey] : key.startsWith("errors.") ? bg["errors.internal"] : key;
  if (!params) return template;
  return template.replace(/\{(\w+)\}/g, (match, name: string) =>
    name in params ? String(params[name]) : match,
  );
}
