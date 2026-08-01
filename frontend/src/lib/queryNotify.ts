/** TanStack Query's notifyManager always defers cache-subscriber
 * notifications to a macrotask (query-core's notifyManager.ts: `scheduleFn`
 * defaults to `setTimeout(fn, 0)`) - never synchronously, not even inside
 * React's `flushSync`, and not before `invalidateQueries`'s own promise
 * settles (confirmed by reading the installed @tanstack/query-core source
 * and reproducing in a regression test). A component whose data comes from
 * `useQuery` (e.g. AuthContext's `me`) can still read the *previous* value
 * for one macrotask after a synchronous `setQueryData` call returns.
 *
 * Call this after `setQueryData` and before anything that reactively
 * depends on the new value having already propagated - e.g. `navigate()`
 * right after logging in, where App.tsx's `RequireAuth`/`RequireVendorAuth`
 * would otherwise still see the old (often empty) `me` and bounce back to
 * the login page. */
export function waitForQueryNotifications(): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, 0));
}
