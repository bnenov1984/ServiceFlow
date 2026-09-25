import { test, expect } from '@playwright/test';
import { enterRepairFlow, getOwnerCredentials, loginAsOwner } from '../support/login';

test('owner delivers an order and issues an invoice for it', async ({ page }) => {
  const { email, password } = getOwnerCredentials();

  const unique = Date.now();
  const customerName = `E2E Invoice Customer ${unique}`;
  const customerPhone = `08${String(unique).slice(-8)}`;
  const complaint = `E2E тест оплакване ${unique}`;

  await loginAsOwner(page, email, password);

  await enterRepairFlow(page);

  // Setup: Issue requires a complete seller (company.service.py's issue() —
  // address + a checksum-valid EIK, errors.invoices.seller_incomplete
  // otherwise). A freshly seeded company has neither. "130489869" is the
  // same known-valid test EIK the backend invoice test suite already uses
  // (test_invoice_issue.py and siblings). The buyer side needs no such
  // setup: our test customer stays an individual (NewCustomerForm's
  // default), and _buyer_snapshot only demands address/EIK for company
  // buyers.
  await page.goto('/settings/company');
  await page.getByLabel('Адрес').fill('гр. София, ул. Тест 1');
  await page.getByLabel('ЕИК / БУЛСТАТ').fill('130489869');
  // exact: true — CompanyRequisitesPage also renders a "Запази гаранцията"
  // button (WarrantyDefaultsSection, a separate form on the same page).
  await page.getByRole('button', { name: 'Запази', exact: true }).click();
  await expect(page.getByText('Данните за фирмата са запазени.')).toBeVisible();

  // Get a real order onto the board (same flow as order-intake.spec.ts /
  // order-delivery.spec.ts) and deliver it — invoicing is exercised against
  // a delivered order, the realistic point in the lifecycle to bill it.
  await page.goto('/orders');
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

  // received -> diagnostics -> repair -> ready, the matrix's plain "ok"
  // chain (transition-matrix.json), same as order-delivery.spec.ts.
  for (const step of ['Диагностика', 'Ремонт', 'Готова']) {
    await page
      .getByRole('button', { name: 'Промени статус' })
      .click();

    await page
      .getByRole('menuitem', { name: step, exact: true })
      .click();

    await expect(page.getByText(step, { exact: true })).toBeVisible();

    // Wait for each transition's own POST -> refreshOrder() chain to fully
    // settle before starting the next one — OrderHeader.tsx used to let a
    // stale chain's close() clobber a *later* click's pending dialog state
    // (fixed; see order-delivery.spec.ts / frontend/e2e/CLAUDE.md), this is
    // defense-in-depth plus more realistic pacing.
    await page.waitForLoadState('networkidle');
  }

  // ready -> completed has its own dedicated primary button, not the
  // "Промени статус" dropdown (audit correction, 2026-09-25 — see
  // order-delivery.spec.ts / frontend/e2e/CLAUDE.md).
  await page
    .getByRole('button', { name: 'Приключи поръчката' })
    .click();

  // Dialog.tsx's <h2> title isn't aria-labelledby'd to the <dialog> element
  // (a real, pre-existing accessibility gap), so the dialog carries no
  // accessible name — check role and visible title text separately.
  await expect(page.getByRole('dialog')).toBeVisible();
  await expect(page.getByText('Приключване на поръчката')).toBeVisible();

  await page
    .getByRole('spinbutton', { name: 'Гаранция (дни)' })
    .fill('180');

  await page
    .getByRole('button', { name: 'Приключи', exact: true })
    .click();

  await expect(page.getByText('Приключена', { exact: true })).toBeVisible();

  // Invoice: scoped to the "Фактура" card specifically — the order page
  // has several other sections with their own identically-labeled "Добави"
  // buttons (Задачи, Аксесоари), so an unscoped getByRole('button', {name:
  // 'Добави'}) would be ambiguous.
  const invoiceCard = page
    .getByRole('heading', { name: 'Фактура', level: 3 })
    .locator('..');

  await invoiceCard
    .getByRole('button', { name: 'Създай чернова' })
    .click();

  // The new draft doesn't reliably land expanded — open it explicitly
  // rather than assume InvoiceEntry's defaultOpen took effect.
  await invoiceCard
    .getByRole('button', { name: 'Отвори' })
    .click();

  // This order has no part/labor lines (asset type "Друго", nothing added
  // at intake), so the draft starts empty and needs a manual line before
  // Issue accepts it (InvoiceDraftEditor's Issue button is disabled while
  // empty; the backend rejects an empty draft with errors.invoices.empty
  // regardless).
  await invoiceCard
    .getByRole('textbox', { name: 'Описание…' })
    .fill('Диагностика и ремонт');

  await invoiceCard
    .getByRole('spinbutton', { name: 'Цена (€)' })
    .fill('50');

  await invoiceCard
    .getByRole('button', { name: 'Добави' })
    .click();

  // Issue posts against the server-persisted draft, not local unsaved
  // edits (InvoiceDraftEditor's submitIssue never saves first) — Save is
  // required before Issue, not just before leaving the editor.
  await invoiceCard
    .getByRole('button', { name: 'Запази' })
    .click();

  await expect(page.getByText('Черновата е запазена.')).toBeVisible();

  await invoiceCard
    .getByRole('button', { name: 'Издай фактура' })
    .click();

  const issueDialog = page.getByRole('dialog');
  await expect(issueDialog).toBeVisible();
  await expect(page.getByText('Издаване на фактура')).toBeVisible();

  await issueDialog
    .getByRole('button', { name: 'Издай фактура' })
    .click();

  await expect(page.getByText('Фактурата е издадена.')).toBeVisible();
  await expect(invoiceCard.getByText('Издадена', { exact: true })).toBeVisible();
});
