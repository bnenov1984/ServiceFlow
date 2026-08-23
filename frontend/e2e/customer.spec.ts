import { test, expect } from '@playwright/test';

test('owner can create a customer', async ({ page }) => {
  const ownerEmail = process.env.E2E_OWNER_EMAIL;
  const ownerPassword = process.env.E2E_OWNER_PASSWORD;

  if (!ownerEmail || !ownerPassword) {
    throw new Error('E2E owner credentials are not configured');
  }

  const unique = Date.now();
  const customerName = `E2E Customer ${unique}`;
  const customerPhone = `08${String(unique).slice(-8)}`;

  await page.goto('/');

  await page
    .getByRole('textbox', { name: 'Имейл' })
    .fill(ownerEmail);

  await page
    .getByRole('textbox', { name: 'Парола' })
    .fill(ownerPassword);

  await page
    .getByRole('button', { name: 'Влез' })
    .click();

  await expect(page).toHaveURL('/choose-app');

  await page
    .getByRole('button', { name: 'RepairFlow' })
    .click();

  await expect(page).toHaveURL('/');

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