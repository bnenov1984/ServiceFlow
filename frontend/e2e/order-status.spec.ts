import { test, expect } from '@playwright/test';
import { getOwnerCredentials, loginAsOwner } from './support/login';

test('owner advances an order from Приета to Диагностика via the status menu', async ({ page }) => {
  const { email, password } = getOwnerCredentials();

  const unique = Date.now();
  const customerName = `E2E Status Customer ${unique}`;
  const customerPhone = `08${String(unique).slice(-8)}`;
  const complaint = `E2E тест оплакване ${unique}`;

  await loginAsOwner(page, email, password);

  await page
    .getByRole('button', { name: 'RepairFlow' })
    .click();

  await expect(page).toHaveURL('/');

  // Get a real order onto the board first (same flow as order-intake.spec.ts)
  // — the status menu only has something to test once an order exists.
  await page
    .getByRole('button', { name: '+ Нова поръчка' })
    .click();

  await page
    .getByRole('button', { name: '+ Нов клиент' })
    .click();

  await page
    .getByRole('textbox', { name: 'Име', exact: true })
    .fill(customerName);

  await page
    .getByRole('textbox', { name: 'Телефон' })
    .fill(customerPhone);

  await page
    .getByRole('button', { name: 'Продължи' })
    .click();

  await expect(page.getByText(customerName)).toBeVisible();

  await page
    .getByRole('button', { name: '+ Нов актив' })
    .click();

  await page
    .getByRole('button', { name: 'Друго' })
    .click();

  await page
    .getByRole('button', { name: 'Продължи' })
    .click();

  await page
    .locator('textarea')
    .fill(complaint);

  await page
    .getByRole('button', { name: 'Създай поръчка' })
    .click();

  await expect(page).toHaveURL(/\/orders\/[0-9a-f-]{36}$/);

  // A freshly created order starts at "received" ("Приета", docs/01 BR-1) —
  // confirm the starting state before changing it.
  await expect(page.getByText('Приета', { exact: true })).toBeVisible();

  // "received" -> "diagnostics" is the matrix's plain "ok" next step (no
  // reason/approval/delivery dialog attached to it — see OrderHeader.tsx's
  // requestTransition), the simplest real status change to drive end to end.
  await page
    .getByRole('button', { name: 'Промени статус' })
    .click();

  await page
    .getByRole('menuitem', { name: 'Диагностика' })
    .click();

  await expect(page.getByText('Диагностика', { exact: true })).toBeVisible();
  await expect(page.getByText('Приета', { exact: true })).not.toBeVisible();
});
