import { test, expect, type Page } from '@playwright/test';
import { enterRepairFlow, getOwnerCredentials, loginAsOwner } from '../support/login';

// Regression for PO bugs #23/#30: a change made in one view (orders list,
// intake) must show in the other views immediately — not after the global
// 30 s staleTime (main.tsx) runs out. Every step below navigates client-side
// on purpose: a full page load starts with an empty cache and hides the bug.

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
  await page.getByRole('button', { name: 'Списък' }).click();
}

const listRow = (page: Page, number: string) =>
  page.getByRole('listitem').filter({ has: page.getByRole('link', { name: number, exact: true }) });

test.beforeEach(async ({ page }) => {
  const { email, password } = getOwnerCredentials();
  await loginAsOwner(page, email, password);
  await enterRepairFlow(page);
});

test('a new order shows in the orders list right after intake', async ({ page }) => {
  const number = await createOrder(page);
  await openOrdersList(page);
  await expect(listRow(page, number)).toBeVisible({ timeout: 5000 });
});

test('a status changed from the orders list shows on the order page (#23)', async ({ page }) => {
  const number = await createOrder(page);
  // Reload so the list is fetched fresh below — this test is about the order
  // page's cache only, not the intake → list case covered above.
  await page.reload();
  await expect(page.getByText('Приета', { exact: true })).toBeVisible();
  await openOrdersList(page);

  await listRow(page, number).getByRole('button', { name: 'Диагностика', exact: true }).click();
  await page.waitForLoadState('networkidle');
  await page.getByRole('link', { name: number, exact: true }).click();

  await expect(page.getByText('Диагностика', { exact: true })).toBeVisible({ timeout: 5000 });
  await expect(page.getByText('Приета', { exact: true })).not.toBeVisible();
});

test('Чака клиент → Чака части from the orders list shows on the order page (#30)', async ({ page }) => {
  const number = await createOrder(page);
  for (const status of ['Диагностика', 'Чака клиент']) {
    await page.getByRole('button', { name: 'Промени статус' }).click();
    await page.getByRole('menuitem', { name: status }).click();
    await page.waitForLoadState('networkidle');
  }
  await page.reload();
  await expect(page.getByText('Чака клиент', { exact: true })).toBeVisible();
  await openOrdersList(page);

  await listRow(page, number).getByRole('button', { name: 'Чака части', exact: true }).click();
  await page.getByRole('button', { name: 'Запиши одобрение' }).click();
  await page.waitForLoadState('networkidle');
  await page.getByRole('link', { name: number, exact: true }).click();

  await expect(page.getByText('Чака части', { exact: true })).toBeVisible({ timeout: 5000 });
  await expect(page.getByText('Чака клиент', { exact: true })).not.toBeVisible();
});
