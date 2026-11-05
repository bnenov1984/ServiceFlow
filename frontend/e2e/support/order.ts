import { type Page } from '@playwright/test';

/**
 * order-workflow-revamp WP-G (Q1/Q2a/Q2b/Q2c): a freshly created order sits
 * in НОВА (code `received`), which has no "Промени статус" dropdown at all
 * — only a dedicated ПРИЕМИ button, which opens a technician picker
 * (pre-filled only when intake itself already picked one, which none of
 * the specs using this helper do) and submits the technician assignment
 * and the move to Диагностика in one request. Every spec that used to
 * click straight through "Промени статус" → "Диагностика" on a brand-new
 * order needs this instead; every later transition in the same test still
 * uses the regular dropdown, unaffected by this WP.
 *
 * Picks whichever technician sorts first (`{ index: 1 }` — index 0 is the
 * picker's own "Без назначен" placeholder) since these specs don't care
 * which one, only that the order actually reaches Диагностика.
 */
export async function acceptIntoDiagnostics(page: Page): Promise<void> {
  await page.getByRole('button', { name: 'Приеми' }).click();
  await page.getByLabel('Техник').selectOption({ index: 1 });
  await page.getByRole('dialog').getByRole('button', { name: 'Приеми' }).click();
  await page.waitForLoadState('networkidle');
}
