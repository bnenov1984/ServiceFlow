import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { RequireVendorAuth } from "./RequireVendorAuth";

const mockUseVendorAuth = vi.fn();
vi.mock("./VendorAuthContext", () => ({
  useVendorAuth: () => mockUseVendorAuth(),
}));

function renderGuarded(initialPath: string) {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <Routes>
        <Route path="/vendor/login" element={<div>VENDOR_LOGIN_PAGE</div>} />
        <Route
          path="/vendor/companies"
          element={
            <RequireVendorAuth>
              <div>PROTECTED_CONTENT</div>
            </RequireVendorAuth>
          }
        />
      </Routes>
    </MemoryRouter>,
  );
}

describe("RequireVendorAuth", () => {
  it("shows a loading state while the vendor session is resolving", () => {
    mockUseVendorAuth.mockReturnValue({ me: null, isLoading: true });
    renderGuarded("/vendor/companies");
    expect(screen.queryByText("PROTECTED_CONTENT")).not.toBeInTheDocument();
    expect(screen.queryByText("VENDOR_LOGIN_PAGE")).not.toBeInTheDocument();
  });

  it("redirects to /vendor/login with ?next= when there is no vendor session", () => {
    mockUseVendorAuth.mockReturnValue({ me: null, isLoading: false });
    renderGuarded("/vendor/companies");
    expect(screen.getByText("VENDOR_LOGIN_PAGE")).toBeInTheDocument();
  });

  it("renders children once a vendor session exists", () => {
    mockUseVendorAuth.mockReturnValue({
      me: { platform_admin_id: "p1", name: "Vendor Admin", email: "v@v.bg", csrf_token: "t" },
      isLoading: false,
    });
    renderGuarded("/vendor/companies");
    expect(screen.getByText("PROTECTED_CONTENT")).toBeInTheDocument();
  });
});
