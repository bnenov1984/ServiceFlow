import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { VendorAuthProvider, useVendorAuth } from "./VendorAuthContext";

const mockGet = vi.fn();
const mockPost = vi.fn();
vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../lib/api")>("../lib/api");
  return {
    ...actual,
    api: {
      ...actual.api,
      get: (...args: unknown[]) => mockGet(...args),
      post: (...args: unknown[]) => mockPost(...args),
    },
  };
});

function LogoutButton() {
  const { logout } = useVendorAuth();
  return (
    <button type="button" onClick={() => void logout()}>
      LOGOUT
    </button>
  );
}

describe("VendorAuthContext logout", () => {
  it("removes only vendor-prefixed cache entries, leaving an unrelated tenant entry intact", async () => {
    mockGet.mockResolvedValue({ platform_admin_id: "p1", name: "V", email: "v@v.bg", csrf_token: "t" });
    mockPost.mockResolvedValue({ ok: true });

    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    queryClient.setQueryData(["me"], { user_id: "u1" }); // unrelated tenant cache entry
    queryClient.setQueryData(["vendor", "companies"], [{ id: "c1" }]);

    render(
      <QueryClientProvider client={queryClient}>
        <VendorAuthProvider>
          <LogoutButton />
        </VendorAuthProvider>
      </QueryClientProvider>,
    );

    const user = userEvent.setup();
    await user.click(await screen.findByText("LOGOUT"));

    await waitFor(() => {
      expect(mockPost).toHaveBeenCalledWith("/platform-admin/auth/logout");
    });
    expect(queryClient.getQueryData(["vendor", "companies"])).toBeUndefined();
    expect(queryClient.getQueryData(["me"])).toEqual({ user_id: "u1" });
  });
});
