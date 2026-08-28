import type { Page } from '@playwright/test';

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
