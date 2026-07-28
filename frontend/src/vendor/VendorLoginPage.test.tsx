import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { ApiError } from "../lib/api";
import { VendorLoginPage } from "./VendorLoginPage";

const mockPost = vi.fn();
vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../lib/api")>("../lib/api");
  return { ...actual, api: { ...actual.api, post: (...args: unknown[]) => mockPost(...args) } };
});

const mockRefresh = vi.fn();
vi.mock("./VendorAuthContext", () => ({
  useVendorAuth: () => ({ refresh: mockRefresh, me: null, isLoading: false, logout: vi.fn() }),
}));

function renderLoginAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/vendor/login" element={<VendorLoginPage />} />
        <Route path="/vendor/companies" element={<div>COMPANIES_PAGE</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("VendorLoginPage", () => {
  it("posts credentials to the vendor login endpoint and navigates to ?next= on success", async () => {
    mockPost.mockResolvedValue({ platform_admin_id: "p1", name: "V", email: "v@v.bg", csrf_token: "t" });
    renderLoginAt("/vendor/login?next=%2Fvendor%2Fcompanies%2Fabc");
    const user = userEvent.setup();

    await user.type(screen.getByLabelText(/имейл/i), "v@v.bg");
    await user.type(screen.getByLabelText(/парола/i), "секретна-парола");
    await user.click(screen.getByRole("button", { name: "Вход" }));

    expect(mockPost).toHaveBeenCalledWith("/platform-admin/auth/login", {
      email: "v@v.bg",
      password: "секретна-парола",
    });
    expect(mockRefresh).toHaveBeenCalled();
  });

  it("shows the shared invalid-credentials message on a failed login", async () => {
    mockPost.mockRejectedValue(new ApiError(401, "auth_failed", "errors.auth.invalid_credentials"));
    renderLoginAt("/vendor/login");
    const user = userEvent.setup();

    await user.type(screen.getByLabelText(/имейл/i), "v@v.bg");
    await user.type(screen.getByLabelText(/парола/i), "грешна");
    await user.click(screen.getByRole("button", { name: "Вход" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Грешен имейл или парола.");
  });

  it("shows the shared lockout message when the vendor login is rate-limited", async () => {
    mockPost.mockRejectedValue(new ApiError(429, "auth_failed", "errors.auth.locked_out"));
    renderLoginAt("/vendor/login");
    const user = userEvent.setup();

    await user.type(screen.getByLabelText(/имейл/i), "v@v.bg");
    await user.type(screen.getByLabelText(/парола/i), "нещо");
    await user.click(screen.getByRole("button", { name: "Вход" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/Твърде много опити/);
  });
});
