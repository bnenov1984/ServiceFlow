import { expect, type Page } from '@playwright/test';

export interface OwnerCredentials {
  email: string;
  password: string;
}

export function getOwnerCredentials(): OwnerCredentials {
  const email = process.env.E2E_OWNER_EMAIL;
  const password = process.env.E2E_OWNER_PASSWORD;

  if (!email || !password) {
    throw new Error('E2E owner credentials are not configured');
  }

  return { email, password };
}

export async function loginAsOwner(
  page: Page,
  email: string,
  password: string
): Promise<void> {
  await page.goto('/');

  await page
    .getByRole('textbox', { name: 'Имейл' })
    .fill(email);

  await page
    .getByRole('textbox', { name: 'Парола' })
    .fill(password);

  await page
    .getByRole('button', { name: 'Влез' })
    .click();
}

/**
 * Enters the RepairFlow app from wherever login landed, then waits for the
 * orders workspace.
 *
 * Tolerant of both tenant shapes on purpose. IndexRoute (frontend/src/App.tsx)
 * sends a RepairFlow-only company straight to `/orders` and only shows
 * `/choose-app` when both applications are active — and since the 11.09.2026
 * one-application-per-company decision, a co-entitled company is no longer
 * representable in production (`platform_admin.service.grant_entitlement`).
 * `serviceflow.seed` now seeds RepairFlow only to match, so CI's local tenant
 * skips the chooser, while the long-lived deployed tenant the `e2e` job runs
 * against may still be co-entitled from before that change. One helper covers
 * both rather than forking the specs on which environment they're pointed at.
 *
 * The chooser's five routing branches are unit-tested in
 * `frontend/src/App.routing.test.tsx`, so nothing is lost by not asserting a
 * specific landing here.
 */
export async function enterRepairFlow(page: Page): Promise<void> {
  // Branch on the settled URL, not on a visibility probe: `isVisible()` does
  // not retry, so probing it while login's own client-side redirect is still
  // in flight would report "no chooser" on a tenant that is about to show one,
  // silently skip the click and then time out at /choose-app. Waiting for one
  // of the two known destinations first makes the branch deterministic.
  await page.waitForURL(/\/(orders|choose-app)$/);

  if (new URL(page.url()).pathname === '/choose-app') {
    await page.getByRole('button', { name: 'RepairFlow' }).click();
  }

  await expect(page).toHaveURL('/orders');
}
