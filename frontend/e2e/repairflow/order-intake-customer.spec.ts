import { test, expect } from '@playwright/test';
import { enterRepairFlow, getOwnerCredentials, loginAsOwner } from '../support/login';

test('owner can create a customer', async ({ page }) => {
  const { email, password } = getOwnerCredentials();

  const unique = Date.now();
  const customerName = `E2E Customer ${unique}`;
  const customerPhone = `08${String(unique).slice(-8)}`;

  await loginAsOwner(page, email, password);

  await enterRepairFlow(page);

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