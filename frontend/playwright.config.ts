import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  timeout: 60_000,
  // Historically this absorbed a `toHaveURL('/')` race against IndexRoute's
  // own "/" -> "/orders" redirect (observed ~1-in-4 locally). That race is
  // gone: every spec now enters through `support/login.ts`'s
  // enterRepairFlow(), which waits for '/orders' directly. Retries stay for
  // ordinary cloud-environment flake against the deployed tenant — a genuine
  // bug still fails twice in a row. Revisit if a spec starts passing only on
  // retry: that is a signal, not a success.
  retries: process.env.CI ? 2 : 0,
  // HTML report for CI failure artifacts; 'list' keeps the existing console
  // output unchanged for local/interactive runs.
  reporter: [['list'], ['html', { open: 'never' }]],
  use: {
    baseURL: process.env.E2E_BASE_URL,

    // 'retain-on-failure', not 'on-first-retry': it captures on any failed
    // test, retries or not, which is what a CI failure artifact needs. (The
    // comment here used to claim `retries` was unset — it has been 2 under CI
    // since the artifact-upload work; corrected 20.09.2026.)
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
});