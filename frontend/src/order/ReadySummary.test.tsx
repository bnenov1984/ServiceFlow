import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { api } from "../lib/api";
import { ReadySummary } from "./ReadySummary";

vi.mock("../lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../lib/api")>();
  return { ...actual, api: { ...actual.api, get: vi.fn() } };
});

function renderSummary() {
  vi.mocked(api.get).mockImplementation((path: string) => {
    if (path.endsWith("/part-lines")) {
      return Promise.resolve([
        { id: "p1", name: "Дисплей", qty: 1, unit_price: 100, state: "installed" },
      ]) as never;
    }
    if (path.endsWith("/labor-lines")) {
      return Promise.resolve([
        { id: "l1", description: "Смяна на дисплей", qty: 1, unit_price: 50 },
      ]) as never;
    }
    return Promise.reject(new Error(`unexpected GET ${path}`));
  });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <ReadySummary
        orderId="order-1"
        complaint="Не се включва"
        diagnosis={{
          observed: "Счупен екран", cause: "Падане", recommendation: "Смяна на дисплей",
          estimated_cost: 150, estimated_days: 1, repairable: true,
          approval_required: true, approval: { approved: true },
        }}
        estimatedTotal={150}
        paidAmount={50}
        balance={100}
      />
    </QueryClientProvider>,
  );
}

describe("ReadySummary (Wave 2 Issue 8)", () => {
  it("shows the complaint", async () => {
    renderSummary();
    expect(await screen.findByText("Не се включва")).toBeInTheDocument();
  });

  it("shows the diagnosis recap", async () => {
    renderSummary();
    expect(await screen.findByText("Счупен екран")).toBeInTheDocument();
    expect(screen.getByText("Падане")).toBeInTheDocument();
    expect(screen.getByText("Смяна на дисплей")).toBeInTheDocument();
  });

  it("shows work performed (labor) and parts", async () => {
    renderSummary();
    expect(await screen.findByText("Смяна на дисплей · 50.00 €")).toBeInTheDocument();
    expect(screen.getByText("Дисплей · 100.00 €")).toBeInTheDocument();
  });

  it("shows the total, paid, and balance", async () => {
    renderSummary();
    expect(await screen.findByText("150.00 €")).toBeInTheDocument();
    expect(screen.getByText("50.00 €")).toBeInTheDocument();
    expect(screen.getByText("100.00 €")).toBeInTheDocument();
  });

  it("does not render any editing controls", async () => {
    renderSummary();
    await screen.findByText("Не се включва");
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
  });

  it("shows an empty state when there is no diagnosis yet", async () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    vi.mocked(api.get).mockResolvedValue([]);
    render(
      <QueryClientProvider client={client}>
        <ReadySummary
          orderId="order-1" complaint="x" diagnosis={null}
          estimatedTotal={0} paidAmount={0} balance={0}
        />
      </QueryClientProvider>,
    );
    expect(await screen.findByText("Няма диагноза.")).toBeInTheDocument();
  });
});
