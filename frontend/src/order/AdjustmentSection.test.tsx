import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../lib/api";
import { AdjustmentSection } from "./AdjustmentSection";

vi.mock("../lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../lib/api")>();
  return { ...actual, api: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), put: vi.fn(), delete: vi.fn() } };
});

const mockUseAuth = vi.fn();
vi.mock("../auth/AuthContext", () => ({
  useAuth: () => mockUseAuth(),
}));

beforeEach(() => {
  vi.mocked(api.get).mockReset();
  vi.mocked(api.post).mockReset();
});

interface Adjustment {
  id: string;
  amount: number;
  reason: string;
  created_at: string;
}

function renderSection(adjustments: Adjustment[], isOwner: boolean) {
  mockUseAuth.mockReturnValue({ me: { is_owner: isOwner } });
  vi.mocked(api.get).mockResolvedValue(adjustments);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <AdjustmentSection orderId="order-1" />
    </QueryClientProvider>,
  );
}

describe("AdjustmentSection — WP-I (Q13, resolves docs/01 OQ-5)", () => {
  it("shows the add form for an Owner", async () => {
    renderSection([], true);
    expect(await screen.findByPlaceholderText("Сума €")).toBeInTheDocument();
  });

  it("hides the add form for a non-Owner (historic adjustment present)", async () => {
    renderSection([{ id: "a1", amount: -5, reason: "x", created_at: "2026-11-05T10:00:00Z" }], false);
    await screen.findByText(/x/);
    expect(screen.queryByPlaceholderText("Сума €")).not.toBeInTheDocument();
  });

  it("renders nothing for a non-Owner when there are no adjustments", async () => {
    const { container } = renderSection([], false);
    await waitFor(() => expect(container).toBeEmptyDOMElement());
  });

  it("still shows a historic adjustment to a non-Owner, without an add form", async () => {
    renderSection([{ id: "a1", amount: -20, reason: "Лоялен клиент", created_at: "2026-11-05T10:00:00Z" }], false);

    expect(await screen.findByText(/Лоялен клиент/)).toBeInTheDocument();
    expect(screen.queryByPlaceholderText("Сума €")).not.toBeInTheDocument();
  });

  it("Owner submits a signed amount with a mandatory reason", async () => {
    const user = userEvent.setup();
    vi.mocked(api.post).mockResolvedValue({});
    renderSection([], true);

    await user.type(await screen.findByPlaceholderText("Сума €"), "-20");
    await user.type(screen.getByPlaceholderText("Причина…"), "Лоялен клиент");
    await user.click(screen.getByRole("button", { name: "Добави" }));

    expect(api.post).toHaveBeenCalledWith("/orders/order-1/adjustments", {
      amount: -20, reason: "Лоялен клиент",
    });
  });

  it("does not submit without both an amount and a reason", async () => {
    const user = userEvent.setup();
    renderSection([], true);

    await user.type(await screen.findByPlaceholderText("Сума €"), "-20");
    await user.click(screen.getByRole("button", { name: "Добави" }));

    expect(api.post).not.toHaveBeenCalled();
  });

  it("renders a positive adjustment and a negative one distinctly", async () => {
    renderSection([
      { id: "a1", amount: -20, reason: "Отстъпка", created_at: "2026-11-05T10:00:00Z" },
      { id: "a2", amount: 15, reason: "Допълнителна услуга", created_at: "2026-11-05T10:01:00Z" },
    ], true);

    expect(await screen.findByText(/-20.00 €/)).toBeInTheDocument();
    expect(screen.getByText(/\+15.00 €/)).toBeInTheDocument();
  });
});
