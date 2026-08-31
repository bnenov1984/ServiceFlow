import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { api } from "../lib/api";
import { PromisedDateBlock } from "./PromisedDateBlock";

vi.mock("../lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../lib/api")>();
  return { ...actual, api: { ...actual.api, patch: vi.fn() } };
});

function renderBlock(promisedOn: string | null, editable = true) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <PromisedDateBlock orderId="order-1" promisedOn={promisedOn} editable={editable} />
    </QueryClientProvider>,
  );
}

describe("PromisedDateBlock (Wave 2 Issue 25)", () => {
  it("shows a placeholder when no date is set", () => {
    renderBlock(null);
    expect(screen.getByText("Няма зададена дата.")).toBeInTheDocument();
  });

  it("shows the stored date when set", () => {
    renderBlock("2026-09-15");
    expect(screen.getByText("2026-09-15")).toBeInTheDocument();
  });

  it("hides the change action when not editable (terminal order)", () => {
    renderBlock(null, false);
    expect(screen.queryByText("Промени")).not.toBeInTheDocument();
  });

  it("editing and picking a chip PATCHes /orders/{id} with promised_on", async () => {
    const user = userEvent.setup();
    vi.mocked(api.patch).mockResolvedValue({});
    renderBlock(null);

    await user.click(screen.getByText("Промени"));
    await user.click(screen.getByText("Днес"));

    expect(api.patch).toHaveBeenCalledWith(
      "/orders/order-1",
      expect.objectContaining({ promised_on: expect.any(String) }),
    );
  });
});
