import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ToastProvider } from "../components/Toast";
import { ApiError, api } from "../lib/api";
import { PartLinesSection } from "./PartLinesSection";

vi.mock("../lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../lib/api")>();
  return { ...actual, api: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), put: vi.fn(), delete: vi.fn() } };
});

beforeEach(() => {
  vi.mocked(api.get).mockReset();
  vi.mocked(api.post).mockReset();
  vi.mocked(api.patch).mockReset();
});

interface Line {
  id: string;
  name: string;
  qty: number;
  unit_cost: number;
  unit_price: number;
  state: string;
}

const DISPLAY = { name: "Дисплей Samsung A52", unit_price: 85, state: "ordered" };
const BATTERY = { name: "Батерия", unit_price: 32, state: "received" };

function line(overrides: Partial<Line> & { id: string }): Line {
  return { name: "Част", qty: 1, unit_cost: 0, unit_price: 0, state: "needed", ...overrides };
}

function renderSection(initialLines: Line[]) {
  vi.mocked(api.get).mockResolvedValue(initialLines);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <ToastProvider>
        <PartLinesSection orderId="order-1" />
      </ToastProvider>
    </QueryClientProvider>,
  );
}

describe("PartLinesSection — status selector", () => {
  it("displays the current status of each part", async () => {
    renderSection([
      line({ id: "p1", ...DISPLAY }),
      line({ id: "p2", ...BATTERY }),
    ]);

    const displaySelect = await screen.findByRole("combobox", { name: /Дисплей Samsung A52/ });
    const batterySelect = screen.getByRole("combobox", { name: /Батерия/ });
    expect(displaySelect).toHaveValue("ordered");
    expect(batterySelect).toHaveValue("received");
  });

  it("is a real interactive control with an accessible name identifying the part", async () => {
    renderSection([line({ id: "p1", ...DISPLAY })]);

    const select = await screen.findByRole("combobox", { name: /Статус на частта/ });
    expect(select).toHaveAccessibleName(expect.stringContaining(DISPLAY.name));
    expect(select.tagName).toBe("SELECT");
  });

  it("exposes the actual domain statuses as selectable options, not an invented subset", async () => {
    renderSection([line({ id: "p1", ...DISPLAY })]);

    const select = await screen.findByRole("combobox", { name: /Дисплей Samsung A52/ });
    const options = Array.from(select.querySelectorAll("option")).map((o) => o.textContent);
    expect(options).toEqual(["Нужна", "Поръчана", "Получена", "Монтирана", "Свалена"]);
  });

  it("selecting a status invokes the part-line PATCH mutation with the chosen target state", async () => {
    const user = userEvent.setup();
    vi.mocked(api.patch).mockResolvedValue({});
    renderSection([line({ id: "p1", ...DISPLAY })]);

    const select = await screen.findByRole("combobox", { name: /Дисплей Samsung A52/ });
    await user.selectOptions(select, "Монтирана");

    expect(api.patch).toHaveBeenCalledWith("/part-lines/p1", { state: "installed" });
  });

  it("updates the displayed status after a successful mutation", async () => {
    const user = userEvent.setup();
    vi.mocked(api.patch).mockResolvedValue({});
    renderSection([line({ id: "p1", ...DISPLAY })]);

    vi.mocked(api.get).mockResolvedValue([line({ id: "p1", ...DISPLAY, state: "installed" })]);

    const select = await screen.findByRole("combobox", { name: /Дисплей Samsung A52/ });
    await user.selectOptions(select, "Монтирана");

    await waitFor(() => expect(select).toHaveValue("installed"));
  });

  it("changing one part's status leaves other parts untouched", async () => {
    const user = userEvent.setup();
    vi.mocked(api.patch).mockResolvedValue({});
    renderSection([
      line({ id: "p1", ...DISPLAY }),
      line({ id: "p2", ...BATTERY }),
    ]);

    const displaySelect = await screen.findByRole("combobox", { name: /Дисплей Samsung A52/ });
    const batterySelect = screen.getByRole("combobox", { name: /Батерия/ });
    await user.selectOptions(displaySelect, "Монтирана");

    expect(api.patch).toHaveBeenCalledTimes(1);
    expect(api.patch).toHaveBeenCalledWith("/part-lines/p1", { state: "installed" });
    expect(batterySelect).toHaveValue("received");
  });

  it("prevents a duplicate submission while a change is still pending for that part", async () => {
    const user = userEvent.setup();
    let resolvePatch: (() => void) | undefined;
    vi.mocked(api.patch).mockReturnValue(
      new Promise((resolve) => {
        resolvePatch = () => resolve(undefined);
      }),
    );
    renderSection([line({ id: "p1", ...DISPLAY })]);

    const select = await screen.findByRole("combobox", { name: /Дисплей Samsung A52/ });
    await user.selectOptions(select, "Монтирана");
    expect(select).toBeDisabled();

    // The control is disabled while pending, so a second real user selection
    // is impossible via the UI; only one PATCH should have gone out.
    expect(api.patch).toHaveBeenCalledTimes(1);

    resolvePatch?.();
    await waitFor(() => expect(select).not.toBeDisabled());
  });

  it("does not leave a false status displayed when the mutation fails", async () => {
    const user = userEvent.setup();
    vi.mocked(api.patch).mockRejectedValue(
      new ApiError(400, "invalid_state", "errors.part_lines.invalid_state"),
    );
    renderSection([line({ id: "p1", ...DISPLAY })]);

    const select = await screen.findByRole("combobox", { name: /Дисплей Samsung A52/ });
    await user.selectOptions(select, "Монтирана");

    await screen.findByText("Невалидно състояние на частта.");
    // The query cache was never invalidated on failure, so the select stays
    // bound to the last known-good state from the server.
    expect(select).toHaveValue("ordered");
  });

  it("still supports adding a new part line", async () => {
    const user = userEvent.setup();
    vi.mocked(api.post).mockResolvedValue({});
    renderSection([]);

    await screen.findByText("Няма добавени части.");
    await user.type(screen.getByPlaceholderText("Име на частта…"), "USB-C конектор");
    await user.type(screen.getByPlaceholderText("€"), "18");
    await user.click(screen.getByRole("button", { name: "Добави" }));

    expect(api.post).toHaveBeenCalledWith("/orders/order-1/part-lines", {
      name: "USB-C конектор", unit_price: 18,
    });
  });
});
