/** "Last used app" preference (PO decision, 01.08.2026): only consulted when
 * a company has more than one active app and lands on "/" with no route
 * already implying a choice - single-app companies never read this, their
 * one active module is the only signal needed. Session-scoped and explicitly
 * cleared on login/logout (auth/LoginPage.tsx, auth/AuthContext.tsx) so a
 * preference never leaks from one company to another sharing a browser tab. */
const KEY = "bos.lastApp";

export function getLastApp(): string | null {
  return sessionStorage.getItem(KEY);
}

export function setLastApp(appId: string): void {
  sessionStorage.setItem(KEY, appId);
}

export function clearLastApp(): void {
  sessionStorage.removeItem(KEY);
}
