import { test, expect } from '@playwright/test';
import { enterRepairFlow, getOwnerCredentials, loginAsOwner } from '../support/login';
import { acceptIntoDiagnostics } from '../support/order';

test('owner advances an order from НОВА to Диагностика via ПРИЕМИ', async ({ page }) => {
  const { email, password } = getOwnerCredentials();

  const unique = Date.now();
  const customerName = `E2E Status Customer ${unique}`;
  const customerPhone = `08${String(unique).slice(-8)}`;
  const complaint = `E2E тест оплакване ${unique}`;

  await loginAsOwner(page, email, password);

  await enterRepairFlow(page);

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

  // A freshly created order starts at "received" ("НОВА", docs/01 BR-1;
  // display-renamed from "Приета" by order-workflow-revamp WP-G, Q1) —
  // confirm the starting state before changing it.
  await expect(page.getByText('НОВА', { exact: true })).toBeVisible();

  // НОВА has no "Промени статус" dropdown at all (WP-G, Q2c) — only the
  // dedicated ПРИЕМИ button, which also requires picking a technician
  // (Q2a) before the move to Диагностика is allowed.
  await acceptIntoDiagnostics(page);

  await expect(page.getByText('Диагностика', { exact: true })).toBeVisible();
  await expect(page.getByText('НОВА', { exact: true })).not.toBeVisible();
});
