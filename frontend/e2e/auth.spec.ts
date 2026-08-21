
import { test, expect } from '@playwright/test';

test('owner can login', async ({ page }) => {
  const ownerEmail = process.env.E2E_OWNER_EMAIL;
  const ownerPassword = process.env.E2E_OWNER_PASSWORD;

  if (!ownerEmail || !ownerPassword) {
    throw new Error('E2E owner credentials are not configured');
  }

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

  // Authentication/navigation check
  await expect(page).toHaveURL('/choose-app');

  // Authenticated UI check
  await expect(
    page.getByRole('button', { name: 'RepairFlow' })
  ).toBeVisible();
});

test('owner cannot login with invalid password', async ({ page }) => {
  const ownerEmail = process.env.E2E_OWNER_EMAIL;
  const ownerPassword = process.env.E2E_OWNER_PASSWORD;

  if (!ownerEmail) {
    throw new Error('E2E owner email is not configured');
  }

  await page.goto('/');

  await page
    .getByRole('textbox', { name: 'Имейл' })
    .fill(ownerEmail);

  await page
    .getByRole('textbox', { name: 'Парола' })
    .fill('pass123');

  await page
    .getByRole('button', { name: 'Влез' })
    .click();

  // Authentication/navigation check
  await expect(page).toHaveURL('/login?next=%2F');

  // Authenticated UI check
  await expect(
      await expect(page.getByRole('alert'))
    .toHaveText('Грешен имейл или парола.'));
});