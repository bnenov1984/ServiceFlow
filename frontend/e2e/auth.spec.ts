
import { test, expect } from '@playwright/test';
import { getOwnerCredentials, loginAsOwner } from './support/login';

test('owner can login', async ({ page }) => {
  const { email, password } = getOwnerCredentials();

  await loginAsOwner(page, email, password);

  // Authentication/navigation check
  await expect(page).toHaveURL('/choose-app');

  // Authenticated UI check
  await expect(
    page.getByRole('button', { name: 'RepairFlow' })
  ).toBeVisible();
});

test('owner cannot login with invalid password', async ({ page }) => {
  const ownerEmail = process.env.E2E_OWNER_EMAIL;

  if (!ownerEmail) {
    throw new Error('E2E owner email is not configured');
  }

  await loginAsOwner(page, ownerEmail, 'pass123');

  // Authentication/navigation check
  await expect(page).toHaveURL('/login?next=%2F');

  // Authenticated UI check
  await expect(
      await expect(page.getByRole('alert'))
    .toHaveText('Грешен имейл или парола.'));
});