import { test, expect } from '@playwright/test';
import { getOwnerCredentials, loginAsOwner } from '../support/login';

test('owner delivers an order through the full status lifecycle', async ({ page }) => {
  const { email, password } = getOwnerCredentials();

  const unique = Date.now();
  const customerName = `E2E Delivery Customer ${unique}`;
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

  // Get a real order onto the board first (same flow as order-intake.spec.ts
  // / order-status.spec.ts) — nothing to deliver until one exists.
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
  await expect(page.getByText('Приета', { exact: true })).toBeVisible();

  // received -> diagnostics -> repair -> ready are all plain "ok" transitions
  // (transition-matrix.json) with no reason/approval/delivery dialog
  // attached (OrderHeader.tsx's requestTransition) — three identical menu
  // clicks to reach the one transition that does open a dialog.
  for (const step of ['Диагностика', 'Ремонт', 'Готова']) {
    await page
      .getByRole('button', { name: 'Промени статус' })
      .click();

    // exact: true — "Ремонт" is otherwise a substring match inside
    // "Неремонтируема" (unrepairable), a different menu item entirely.
    await page
      .getByRole('menuitem', { name: step, exact: true })
      .click();

    await expect(page.getByText(step, { exact: true })).toBeVisible();

    // Each transition's own POST -> refreshOrder() (3 invalidated queries)
    // -> close() chain keeps running in the background after the status
    // text above already updated (a real, separately-fixed race in
    // OrderHeader.tsx let a stale chain's close() clobber a *later* click's
    // pending dialog state). The status text updating doesn't guarantee
    // that chain has finished — wait for the network to actually go quiet
    // before starting the next transition, matching realistic pacing
    // instead of racing through four clicks as fast as Playwright can fire
    // them.
    await page.waitForLoadState('networkidle');
  }

  // ready -> delivered opens DeliveryDialog instead of transitioning
  // directly (requestTransition's `to === "delivered"` branch) — accessories
  // is empty for this order (none added at intake) so only warranty/payment
  // show; payment is optional and left blank on purpose. Deliberately never
  // clicks "Печат на протокол" — that path hits a known, separately-tracked
  // fpdf crash (backend/tests/test_protocol.py, xfail(strict=True)) unrelated
  // to the status transition this test verifies.
  await page
    .getByRole('button', { name: 'Промени статус' })
    .click();

  await page
    .getByRole('menuitem', { name: 'Предадена' })
    .click();

  // Dialog.tsx's <h2> title isn't aria-labelledby'd to the <dialog> element
  // (a real, separate accessibility gap, same shape as OrderStep's complaint
  // textarea), so the dialog carries no accessible name for getByRole to
  // match against — check the role and the visible title text separately.
  await expect(page.getByRole('dialog')).toBeVisible();
  await expect(page.getByText('Предаване на клиента')).toBeVisible();

  await page
    .getByRole('spinbutton', { name: 'Гаранция (дни)' })
    .fill('180');

  await page
    .getByRole('button', { name: 'Предай' })
    .click();

  await expect(page.getByText('Предадена', { exact: true })).toBeVisible();
  await expect(page.getByText('Готова', { exact: true })).not.toBeVisible();
});
