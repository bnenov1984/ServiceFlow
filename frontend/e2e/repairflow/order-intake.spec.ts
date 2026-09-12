import { test, expect } from '@playwright/test';
import { getOwnerCredentials, loginAsOwner } from '../support/login';

test('owner can complete order intake from a new customer to a real order', async ({ page }) => {
  const { email, password } = getOwnerCredentials();

  const unique = Date.now();
  const customerName = `E2E Intake Customer ${unique}`;
  const customerPhone = `08${String(unique).slice(-8)}`;
  const complaint = `E2E тест оплакване ${unique}`;

  await loginAsOwner(page, email, password);

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

  // Стъпка 1: Клиент
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

  // Стъпка 2: Актив — "Друго" needs no fields filled; both are optional at
  // the API (no required field defs), so a minimal valid asset is one
  // created with an empty form.
  await page
    .getByRole('button', { name: '+ Нов актив' })
    .click();

  await page
    .getByRole('button', { name: 'Друго' })
    .click();

  await page
    .getByRole('button', { name: 'Продължи' })
    .click();

  // Стъпка 3: Поръчка — the complaint <label> is a plain sibling of the
  // <textarea> with no htmlFor/id/aria-label/placeholder, so it has no
  // accessible name for getByRole/getByLabel to match. This is a real,
  // pre-existing accessibility gap in OrderStep.tsx (not introduced by this
  // test) — the textarea is the only one on the page at this step, so a
  // structural locator is the only reliable option without changing
  // production code.
  await page
    .locator('textarea')
    .fill(complaint);

  await page
    .getByRole('button', { name: 'Създай поръчка' })
    .click();

  // Authentication/navigation check
  await expect(page).toHaveURL(/\/orders\/[0-9a-f-]{36}$/);

  // Authenticated UI check
  await expect(
    page.getByRole('heading', { name: /^№ / })
  ).toBeVisible();
  await expect(page.getByText(complaint)).toBeVisible();
});
