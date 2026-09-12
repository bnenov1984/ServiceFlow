import { test, expect } from '@playwright/test';
import { getOwnerCredentials, loginAsOwner } from '../support/login';

test('owner can create a customer', async ({ page }) => {
  const { email, password } = getOwnerCredentials();

  const unique = Date.now();
  const customerName = `E2E Customer ${unique}`;
  const customerPhone = `08${String(unique).slice(-8)}`;

  await loginAsOwner(page, email, password);

  await expect(page).toHaveURL('/choose-app');

  await page
    .getByRole('button', { name: 'RepairFlow' })
    .click();

  // Not '/' — IndexRoute (App.tsx) immediately re-navigates "/" -> "/orders"
  // once the chooser sets a last-app preference (dual-module company), so
  // '/' never actually settles; asserting it races the app's own redirect.
  await expect(page).toHaveURL('/orders');

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

  await expect(
    page.getByText(customerName)
  ).toBeVisible();
});