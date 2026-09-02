import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "../lib/api";
import { ResetPasswordPage } from "./ResetPasswordPage";

const mockPost = vi.fn();
vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../lib/api")>("../lib/api");
  return { ...actual, api: { ...actual.api, post: (...args: unknown[]) => mockPost(...args) } };
});

function renderPage(path = "/reset-password?token=abc123") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/reset-password" element={<ResetPasswordPage />} />
          <Route path="/login" element={<div>LOGIN_PAGE</div>} />
          <Route path="/forgot-password" element={<div>FORGOT_PASSWORD_PAGE</div>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const VALID_PASSWORD = "нова-парола-123456";

// Sets values directly (fireEvent.change) rather than simulating individual
// keystrokes (user.type) — the only thing under test here is the final
// submitted value/validation outcome, not per-keystroke behavior, and a
// 200+ character value has no reason to go through a slow, per-character
// simulation.
async function fillAndSubmit(
  user: ReturnType<typeof userEvent.setup>,
  password: string,
  confirm: string = password,
) {
  fireEvent.change(screen.getByLabelText("Нова парола"), { target: { value: password } });
  fireEvent.change(screen.getByLabelText("Потвърдете новата парола"), { target: { value: confirm } });
  await user.click(screen.getByRole("button", { name: "Запази новата парола" }));
}

describe("ResetPasswordPage — Tenant Forgot Password V1", () => {
  beforeEach(() => {
    mockPost.mockReset();
  });

  it("reads the token from the query string and submits it with the new password", async () => {
    mockPost.mockResolvedValue({ ok: true });
    renderPage("/reset-password?token=the-raw-token");
    const user = userEvent.setup();

    await fillAndSubmit(user, VALID_PASSWORD);

    expect(mockPost).toHaveBeenCalledWith("/auth/reset-password", {
      token: "the-raw-token", password: VALID_PASSWORD,
    });
  });

  it("shows a missing-token message and disables submit when no token is present", async () => {
    renderPage("/reset-password");

    expect(screen.getByRole("alert")).toHaveTextContent(
      "Липсва или невалидна връзка за възстановяване.",
    );
    expect(screen.getByRole("button", { name: "Запази новата парола" })).toBeDisabled();
  });

  it("rejects a submit when the confirmation does not match", async () => {
    renderPage();
    const user = userEvent.setup();

    await fillAndSubmit(user, VALID_PASSWORD, "различна-парола-123456");

    expect(await screen.findByRole("alert")).toHaveTextContent("Паролите не съвпадат.");
    expect(mockPost).not.toHaveBeenCalled();
  });

  it("rejects a password shorter than the minimum without calling the API", async () => {
    renderPage();
    const user = userEvent.setup();

    await fillAndSubmit(user, "твърде-къса");

    expect(await screen.findByRole("alert")).toHaveTextContent(/12/);
    expect(mockPost).not.toHaveBeenCalled();
  });

  it("rejects a password longer than the maximum without calling the API", async () => {
    renderPage();
    const user = userEvent.setup();
    const tooLong = "a".repeat(201);

    await fillAndSubmit(user, tooLong);

    expect(await screen.findByRole("alert")).toHaveTextContent(/200/);
    expect(mockPost).not.toHaveBeenCalled();
  });

  it("shows a success state and offers navigation to /login, without auto-login", async () => {
    mockPost.mockResolvedValue({ ok: true });
    renderPage();
    const user = userEvent.setup();

    await fillAndSubmit(user, VALID_PASSWORD);

    expect(await screen.findByRole("status")).toHaveTextContent(
      "Паролата е сменена успешно. Влезте с новата си парола.",
    );
    // No auto-login call of any kind — only the one reset-password POST.
    expect(mockPost).toHaveBeenCalledTimes(1);

    await user.click(screen.getByRole("button", { name: "← Обратно към вход" }));
    expect(await screen.findByText("LOGIN_PAGE")).toBeInTheDocument();
  });

  it("shows one generic invalid/expired-token message and a request-new-link action on failure", async () => {
    mockPost.mockRejectedValue(
      new ApiError(400, "auth_failed", "errors.auth.reset_token_invalid"),
    );
    renderPage();
    const user = userEvent.setup();

    await fillAndSubmit(user, VALID_PASSWORD);

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Връзката за възстановяване е невалидна или изтекла.",
    );
    const link = screen.getByRole("link", { name: "Заявете нова връзка за възстановяване" });
    expect(link).toBeInTheDocument();

    await user.click(link);
    expect(await screen.findByText("FORGOT_PASSWORD_PAGE")).toBeInTheDocument();
  });
});
