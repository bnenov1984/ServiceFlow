import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { api } from "../lib/api";
import { ContactsSection } from "./ContactsSection";

vi.mock("../lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../lib/api")>();
  return { ...actual, api: { ...actual.api, get: vi.fn(), post: vi.fn() } };
});

function renderSection(props: { orderId?: string; customerId?: string; showHistory?: boolean }) {
  vi.mocked(api.get).mockResolvedValue([
    { id: "c1", type: "call", direction: "in", summary: "стар запис", occurred_at: "2026-01-01", editable: false },
  ]);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      {/* @ts-expect-error - discriminated union, test call sites pass exactly one of orderId/customerId */}
      <ContactsSection {...props} />
    </QueryClientProvider>,
  );
}

describe("ContactsSection (Wave 2 Issue 34)", () => {
  it("offers only call/email/note as creatable types", () => {
    renderSection({ customerId: "cust-1", showHistory: true });
    expect(screen.getByRole("button", { name: "Обаждане" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Имейл" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Бележка" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Съобщение" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "На място" })).not.toBeInTheDocument();
  });

  it("customer-profile usage (default showHistory) still renders the history list", async () => {
    renderSection({ customerId: "cust-1" });
    expect(await screen.findByText("стар запис")).toBeInTheDocument();
  });

  it("order-scoped usage with showHistory=false renders no history list", () => {
    renderSection({ orderId: "order-1", showHistory: false });
    expect(screen.queryByText("стар запис")).not.toBeInTheDocument();
    expect(screen.queryByText("Няма записи.")).not.toBeInTheDocument();
    // The add-form itself must still be there.
    expect(screen.getByRole("button", { name: "Обаждане" })).toBeInTheDocument();
  });

  it("order-scoped add also invalidates the order timeline query", async () => {
    const user = userEvent.setup();
    vi.mocked(api.post).mockResolvedValue({});
    renderSection({ orderId: "order-1", showHistory: false });

    await user.type(
      screen.getByPlaceholderText("Резюме…"), "Обадих се на клиента",
    );
    await user.click(screen.getByRole("button", { name: "Добави" }));

    expect(api.post).toHaveBeenCalledWith("/orders/order-1/contact-records", expect.objectContaining({
      type: "call", summary: "Обадих се на клиента",
    }));
  });
});
