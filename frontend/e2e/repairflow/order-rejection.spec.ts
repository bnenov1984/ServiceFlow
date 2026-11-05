import { test, expect } from '@playwright/test';
import { enterRepairFlow, getOwnerCredentials, loginAsOwner } from '../support/login';
import { acceptIntoDiagnostics } from '../support/order';

test('owner declines an order with a required reason, reaching a terminal state', async ({ page }) => {
  const { email, password } = getOwnerCredentials();

  const unique = Date.now();
  const customerName = `E2E Reject Customer ${unique}`;
  const customerPhone = `08${String(unique).slice(-8)}`;
  const complaint = `E2E тест оплакване ${unique}`;
  const declineReason = `Клиентът отказа ремонта ${unique}`;

  await loginAsOwner(page, email, password);

  await enterRepairFlow(page);

  // Get a real order onto the board first (same flow as order-intake.spec.ts).
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
  await expect(page.getByText('НОВА', { exact: true })).toBeVisible();

  // НОВА (Q2c) has no "Промени статус" dropdown — ПРИЕМИ (Q2a/Q2b) is the
  // only way to Диагностика, which can still decline from there (docs/02
  // §2: "diagnostics" -> "declined" is OK; matches the rejection journey's
  // "оценка -> отказ").
  await acceptIntoDiagnostics(page);

  await expect(page.getByText('Диагностика', { exact: true })).toBeVisible();

  // "declined" is a TERMINAL_FAILURE_CODES entry (OrderHeader.tsx), rendered
  // in the menu's separate red "failure" section below a divider — still a
  // plain role="menuitem", just visually distinguished.
  await page
    .getByRole('button', { name: 'Промени статус' })
    .click();

  await page
    .getByRole('menuitem', { name: 'Отказана' })
    .click();

  // ReasonDialog: no accessible name on the <dialog> itself (Dialog.tsx's
  // <h2> isn't aria-labelledby'd — a known, separate gap, same shape as the
  // intake complaint textarea) so it's matched by bare role, with title text
  // checked separately, same idiom as order-delivery.spec.ts.
  const dialog = page.getByRole('dialog');
  await expect(dialog).toBeVisible();
  await expect(dialog.getByText('Причина за промяната')).toBeVisible();

  const confirmButton = dialog.getByRole('button', { name: 'Потвърди' });

  // "declined" requires a non-empty reason (service.py: reason_required) —
  // ReasonDialog's own disabled condition should reflect that before any
  // server round-trip happens.
  await expect(confirmButton).toBeDisabled();

  await dialog.locator('textarea').fill(declineReason);
  await expect(confirmButton).toBeEnabled();
  await confirmButton.click();

  await expect(dialog).not.toBeVisible();
  await expect(page.getByText('Отказана', { exact: true })).toBeVisible();
  await expect(page.getByText('Диагностика', { exact: true })).not.toBeVisible();

  // Terminal orders lose the status-change menu (OrderHeader.tsx:
  // `!archived && !orderIsTerminal`) but keep the intake protocol print
  // button available — asserted visible only, not clicked: the delivery
  // protocol has a known separately-tracked fpdf crash
  // (backend/tests/test_protocol.py, xfail(strict=True)) and this test has
  // no reason to risk the intake one being similarly fragile for a first
  // pass at this journey.
  await expect(page.getByRole('button', { name: 'Промени статус' })).not.toBeVisible();
  await expect(page.getByRole('button', { name: 'Печат протокол (приемане)' })).toBeVisible();
});
