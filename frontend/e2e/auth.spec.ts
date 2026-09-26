
import { test, expect } from '@playwright/test';
import { enterRepairFlow, getOwnerCredentials, loginAsOwner } from './support/login';

test('owner can login', async ({ page }) => {
  const { email, password } = getOwnerCredentials();

  await loginAsOwner(page, email, password);

  // Authentication/navigation check. Deliberately not asserting a specific
  // landing URL: IndexRoute (App.tsx) sends a RepairFlow-only company — the
  // shape `serviceflow.seed` now produces and the only one provisioning
  // allows (PO, 11.09.2026) — straight to /orders, while a co-entitled tenant
  // stops at /choose-app first. enterRepairFlow() absorbs that difference, and
  // all five IndexRoute branches are unit-tested in App.routing.test.tsx.
  await enterRepairFlow(page);

  // Authenticated UI check: RepairFlow's own chrome, not the chooser's button.
  await expect(
    page.getByRole('button', { name: '+ Нова поръчка' })
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
  await expect(page.getByRole('alert')).toHaveText('Грешен имейл или парола.');
});