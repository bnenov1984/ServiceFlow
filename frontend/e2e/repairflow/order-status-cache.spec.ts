import { test, expect, type Page } from '@playwright/test';
import { enterRepairFlow, getOwnerCredentials, loginAsOwner } from '../support/login';

// Regression for PO bugs #23/#30: a change made in one view (order page,
// intake) must show in the other views immediately — not after the global
// 30 s staleTime (main.tsx) runs out. Every step below navigates client-side
// on purpose: a full page load starts with an empty cache and hides the bug.
//
// order-workflow-revamp WP-K retired the orders list's own status buttons —
// status changes happen only on the order page now (Q19b), so the #23/#30
// cases (originally "changed from the list, stale on the order page") are
// re-pointed to the only direction that still exists: changed on the order
// page, must not be stale in the orders table. Same shared
// `invalidateOrderViews` fix, same regression risk, opposite direction.

async function createOrder(page: Page): Promise<string> {
  const unique = Date.now();
  await page.getByRole('button', { name: '+ Нова поръчка' }).click();
  await page.getByRole('button', { name: '+ Нов клиент' }).click();
  await page.getByRole('textbox', { name: 'Име', exact: true }).fill(`E2E Cache Customer ${unique}`);
  await page.getByRole('textbox', { name: 'Телефон' }).fill(`08${String(unique).slice(-8)}`);
  await page.getByRole('button', { name: 'Продължи' }).click();
  await page.getByRole('button', { name: '+ Нов актив' }).click();
  await page.getByRole('button', { name: 'Друго' }).click();
  await page.getByRole('button', { name: 'Продължи' }).click();
  await page.locator('textarea').fill(`E2E тест оплакване ${unique}`);
  await page.getByRole('button', { name: 'Създай поръчка' }).click();
  await expect(page).toHaveURL(/\/orders\/[0-9a-f-]{36}$/);
  return (await page.getByRole('heading', { level: 1 }).textContent())!.trim();
}

async function openOrdersList(page: Page) {
  await page.getByRole('link', { name: '← Поръчки' }).click();
}

const tableRow = (page: Page, number: string) =>
  page.getByRole('row').filter({ has: page.getByRole('link', { name: `№ ${number}`, exact: true }) });

test.beforeEach(async ({ page }) => {
  const { email, password } = getOwnerCredentials();
  await loginAsOwner(page, email, password);
  await enterRepairFlow(page);
});

test('a new order shows in the orders list right after intake', async ({ page }) => {
  const number = await createOrder(page);
  await openOrdersList(page);
  await expect(tableRow(page, number)).toBeVisible({ timeout: 5000 });
});

test('a status changed on the order page shows in the orders list (#23)', async ({ page }) => {
  const number = await createOrder(page);
  await page.getByRole('button', { name: 'Промени статус' }).click();
  await page.getByRole('menuitem', { name: 'Диагностика' }).click();
  await page.waitForLoadState('networkidle');

  await openOrdersList(page);
  // Navigated client-side straight from the order page on purpose — a full
  // page load starts with an empty cache and would hide the bug.
  await expect(tableRow(page, number)).toContainText('Диагностика', { timeout: 5000 });
});

test('Чака клиент → Чака части on the order page shows in the orders list (#30)', async ({ page }) => {
  const number = await createOrder(page);
  for (const status of ['Диагностика', 'Чака клиент']) {
    await page.getByRole('button', { name: 'Промени статус' }).click();
    await page.getByRole('menuitem', { name: status }).click();
    await page.waitForLoadState('networkidle');
  }
  await page.getByRole('button', { name: 'Промени статус' }).click();
  await page.getByRole('menuitem', { name: 'Чака части' }).click();
  await page.getByRole('button', { name: 'Запиши одобрение' }).click();
  await page.waitForLoadState('networkidle');

  await openOrdersList(page);
  await expect(tableRow(page, number)).toContainText('Чака части', { timeout: 5000 });
});
