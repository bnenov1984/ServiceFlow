/**
 * Thin fetch wrapper (docs/15 §5.1): credentials included, CSRF header on
 * mutations, docs/09 §1 error envelope parsed into ApiError with a message_key
 * the catalog renders. The CSRF token is set by AuthProvider after /auth/me.
 *
 * Two independent CSRF slots, not one: the tenant app and the Vendor Console
 * (business-os/18, ADR-BOS-009) are structurally separate sessions that can
 * both be alive in the same tab (client-side routing between them never
 * reloads the page). Sharing one `csrfToken` variable would mean whichever
 * logged in most recently silently overwrites the other's token, breaking
 * that other session's next mutation — so the vendor plane gets its own slot,
 * selected by path prefix.
 */

export interface FieldError {
  loc: string[] | string;
  type: string;
}

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    public messageKey: string,
    public params: Record<string, string | number> = {},
    public fieldErrors: FieldError[] = [],
  ) {
    super(messageKey);
  }
}
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";
let csrfToken: string | null = null;
let vendorCsrfToken: string | null = null;

export function setCsrfToken(token: string | null): void {
  csrfToken = token;
}

export function setVendorCsrfToken(token: string | null): void {
  vendorCsrfToken = token;
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const headers: Record<string, string> = {};
  const init: RequestInit = { method, credentials: "include", headers };

  if (method !== "GET") {
    const token = path.startsWith("/platform-admin") ? vendorCsrfToken : csrfToken;
    if (token) headers["X-CSRF-Token"] = token;
    if (body instanceof FormData) {
      init.body = body; // browser sets multipart boundary itself
    } else if (body !== undefined) {
      headers["Content-Type"] = "application/json";
      init.body = JSON.stringify(body);
    }
  }

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/api/v1${path}`, init);
  } catch {
    throw new ApiError(0, "network", "health.unreachable");
  }

  if (!response.ok) {
    let detail: Record<string, unknown> = {};
    try {
      const parsed: unknown = await response.json();
      if (parsed && typeof parsed === "object") {
        const outer = parsed as Record<string, unknown>;
        detail = (outer.detail && typeof outer.detail === "object"
          ? outer.detail
          : outer) as Record<string, unknown>;
      }
    } catch {
      // non-JSON error body: fall through to generic
    }
    throw new ApiError(
      response.status,
      String(detail.code ?? "unknown"),
      String(detail.message_key ?? "errors.internal"),
      (detail.params as Record<string, string | number>) ?? {},
      (detail.field_errors as FieldError[]) ?? [],
    );
  }

  if (response.status === 204) return undefined as T;
  const contentType = response.headers.get("content-type") ?? "";
  if (!contentType.includes("application/json")) {
    return (await response.blob()) as T;
  }
  return (await response.json()) as T;
}

export const api = {
  get: <T>(path: string) => request<T>("GET", path),
  post: <T>(path: string, body?: unknown) => request<T>("POST", path, body),
  patch: <T>(path: string, body?: unknown) => request<T>("PATCH", path, body),
  put: <T>(path: string, body?: unknown) => request<T>("PUT", path, body),
  delete: <T>(path: string) => request<T>("DELETE", path),
};
