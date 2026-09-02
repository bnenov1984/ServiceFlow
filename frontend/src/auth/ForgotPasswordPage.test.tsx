import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "../lib/api";
import { ForgotPasswordPage } from "./ForgotPasswordPage";

const mockPost = vi.fn();
vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../lib/api")>("../lib/api");
  return { ...actual, api: { ...actual.api, post: (...args: unknown[]) => mockPost(...args) } };
});

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/forgot-password"]}>
        <Routes>
          <Route path="/forgot-password" element={<ForgotPasswordPage />} />
          <Route path="/login" element={<div>LOGIN_PAGE</div>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("ForgotPasswordPage — Tenant Forgot Password V1", () => {
  beforeEach(() => {
    mockPost.mockReset();
  });

  it("submits the entered email to POST /auth/forgot-password", async () => {
    mockPost.mockResolvedValue({ ok: true });
    renderPage();
    const user = userEvent.setup();

    await user.type(screen.getByLabelText("Имейл"), "ivan@shop.bg");
    await user.click(screen.getByRole("button", { name: "Изпрати" }));

    expect(mockPost).toHaveBeenCalledWith("/auth/forgot-password", { email: "ivan@shop.bg" });
  });

  it("shows the generic success message after a successful HTTP response, regardless of what happened server-side", async () => {
    mockPost.mockResolvedValue({ ok: true });
    renderPage();
    const user = userEvent.setup();

    await user.type(screen.getByLabelText("Имейл"), "nobody@nowhere.bg");
    await user.click(screen.getByRole("button", { name: "Изпрати" }));

    expect(await screen.findByRole("status")).toHaveTextContent(
      "Ако съществува акаунт с този имейл, изпратихме инструкции за възстановяване на паролата.",
    );
    // The form itself is gone — nothing here ever reveals whether the
    // account existed, e.g. no per-outcome branching in the UI.
    expect(screen.queryByLabelText("Имейл")).not.toBeInTheDocument();
  });

  it("the success copy is identical for two different emails — no account-existence leak", async () => {
    mockPost.mockResolvedValue({ ok: true });

    const { unmount } = renderPage();
    const user1 = userEvent.setup();
    await user1.type(screen.getByLabelText("Имейл"), "known@shop.bg");
    await user1.click(screen.getByRole("button", { name: "Изпрати" }));
    const firstMessage = (await screen.findByRole("status")).textContent;
    unmount();

    renderPage();
    const user2 = userEvent.setup();
    await user2.type(screen.getByLabelText("Имейл"), "unknown@nowhere.bg");
    await user2.click(screen.getByRole("button", { name: "Изпрати" }));
    const secondMessage = (await screen.findByRole("status")).textContent;

    expect(firstMessage).toEqual(secondMessage);
  });

  it("shows an error and does not fake a success message on a transport/server failure", async () => {
    mockPost.mockRejectedValue(new ApiError(500, "internal_error", "errors.internal"));
    renderPage();
    const user = userEvent.setup();

    await user.type(screen.getByLabelText("Имейл"), "ivan@shop.bg");
    await user.click(screen.getByRole("button", { name: "Изпрати" }));

    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("allows navigating back to login", async () => {
    renderPage();
    const user = userEvent.setup();

    await user.click(screen.getByRole("link", { name: "← Обратно към вход" }));

    expect(await screen.findByText("LOGIN_PAGE")).toBeInTheDocument();
  });
});
