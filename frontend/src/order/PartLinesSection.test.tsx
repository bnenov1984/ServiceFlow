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

// CatalogItemPicker (rendered by PartLinesSection) reads useAuth() itself,
// for its own Owner-only quick-add shortcut — unrelated to anything WP-J
// added to PartLinesSection, but still needed for it to render at all.
const mockUseAuth = vi.fn();
vi.mock("../auth/AuthContext", () => ({
  useAuth: () => mockUseAuth(),
}));

beforeEach(() => {
  vi.mocked(api.get).mockReset();
  vi.mocked(api.post).mockReset();
  vi.mocked(api.patch).mockReset();
  mockUseAuth.mockReturnValue({ me: { is_owner: false } });
});

interface Line {
  id: string;
  catalog_item_id: string | null;
  name: string;
  code: string | null;
  qty: number;
  unit_cost: number;
  unit_price: number;
  state: string;
  has_warranty: boolean;
  suggested_status?: string | null;
}

interface CatalogItem {
  id: string;
  kind: "part" | "labor";
  name: string;
  code: string | null;
  unit: "pcs" | "hour";
  sale_price: number;
  unit_cost: number | null;
  archived: boolean;
}

const DISPLAY = { name: "Дисплей Samsung A52", unit_price: 85, state: "ordered" };
const BATTERY = { name: "Батерия", unit_price: 32, state: "installed" };

function line(overrides: Partial<Line> & { id: string }): Line {
  return {
    catalog_item_id: "cat-1", code: null, name: "Част", qty: 1, unit_cost: 0, unit_price: 0,
    state: "issued", has_warranty: true, ...overrides,
  };
}

function catalogItem(overrides: Partial<CatalogItem> & { id: string; name: string }): CatalogItem {
  return {
    kind: "part", code: null, unit: "pcs", sale_price: 0, unit_cost: null, archived: false,
    ...overrides,
  };
}

// One catalog item ("Дисплей Samsung A52", 85 €) — enough for every test
// below that adds a new line via the picker.
const DEFAULT_CATALOG = [catalogItem({ id: "cat-1", name: "Дисплей Samsung A52", sale_price: 85 })];

function mockGet(lines: Line[], catalogItems: CatalogItem[] = DEFAULT_CATALOG) {
  vi.mocked(api.get).mockImplementation((path: string) => {
    if (path.startsWith("/catalog-items")) return Promise.resolve(catalogItems);
    return Promise.resolve(lines);
  });
}

function renderSection(initialLines: Line[], addLineBlockedHint: string | null = null) {
  mockGet(initialLines);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <ToastProvider>
        <PartLinesSection orderId="order-1" addLineBlockedHint={addLineBlockedHint} />
      </ToastProvider>
    </QueryClientProvider>,
  );
}

describe("PartLinesSection — status selector (WP-J: 3-state model)", () => {
  it("displays the current status of each part", async () => {
    renderSection([
      line({ id: "p1", ...DISPLAY }),
      line({ id: "p2", ...BATTERY }),
    ]);

    const displaySelect = await screen.findByRole("combobox", { name: /Дисплей Samsung A52/ });
    const batterySelect = screen.getByRole("combobox", { name: /Батерия/ });
    expect(displaySelect).toHaveValue("ordered");
    expect(batterySelect).toHaveValue("installed");
  });

  it("is a real interactive control with an accessible name identifying the part", async () => {
    renderSection([line({ id: "p1", ...DISPLAY })]);

    const select = await screen.findByRole("combobox", { name: /Статус на частта/ });
    expect(select).toHaveAccessibleName(expect.stringContaining(DISPLAY.name));
    expect(select.tagName).toBe("SELECT");
  });

  it("exposes exactly the three current statuses as selectable options (Q15)", async () => {
    renderSection([line({ id: "p1", ...DISPLAY })]);

    const select = await screen.findByRole("combobox", { name: /Дисплей Samsung A52/ });
    const options = Array.from(select.querySelectorAll("option")).map((o) => o.textContent);
    expect(options).toEqual(["Издадена", "Поръчана", "Монтирана"]);
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

    mockGet([line({ id: "p1", ...DISPLAY, state: "installed" })]);

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
    expect(batterySelect).toHaveValue("installed");
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
});

describe("PartLinesSection — add form (Q15b: two buttons, Q14c: warranty checkbox)", () => {
  it("adds a line via the „От наличност“ button with state=issued and the checked warranty default", async () => {
    const user = userEvent.setup();
    vi.mocked(api.post).mockResolvedValue({});
    renderSection([]);

    await screen.findByText("Няма добавени части.");
    expect(screen.getByLabelText("Гаранция")).toBeChecked();

    await screen.findByRole("option", { name: /Дисплей Samsung A52/ });
    await user.selectOptions(screen.getByRole("combobox"), "cat-1");
    await user.click(screen.getByRole("button", { name: "От наличност" }));

    expect(api.post).toHaveBeenCalledWith("/orders/order-1/part-lines", {
      catalog_item_id: "cat-1", qty: 1, state: "issued", has_warranty: true,
    });
  });

  it("adds a line via the „Поръчай“ button with state=ordered", async () => {
    const user = userEvent.setup();
    vi.mocked(api.post).mockResolvedValue({});
    renderSection([]);

    await screen.findByRole("option", { name: /Дисплей Samsung A52/ });
    await user.selectOptions(screen.getByRole("combobox"), "cat-1");
    await user.click(screen.getByRole("button", { name: "Поръчай" }));

    expect(api.post).toHaveBeenCalledWith("/orders/order-1/part-lines", {
      catalog_item_id: "cat-1", qty: 1, state: "ordered", has_warranty: true,
    });
  });

  it("unchecking the warranty box sends has_warranty: false", async () => {
    const user = userEvent.setup();
    vi.mocked(api.post).mockResolvedValue({});
    renderSection([]);

    await user.click(screen.getByLabelText("Гаранция"));
    await screen.findByRole("option", { name: /Дисплей Samsung A52/ });
    await user.selectOptions(screen.getByRole("combobox"), "cat-1");
    await user.click(screen.getByRole("button", { name: "От наличност" }));

    expect(api.post).toHaveBeenCalledWith("/orders/order-1/part-lines", {
      catalog_item_id: "cat-1", qty: 1, state: "issued", has_warranty: false,
    });
  });

  it("shows the blocked hint instead of the picker when the order's status disallows new lines", async () => {
    renderSection([], "Редове могат да се добавят само в статус Диагностика…");

    expect(await screen.findByText("Редове могат да се добавят само в статус Диагностика…"))
      .toBeInTheDocument();
    expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
  });

  it("existing lines still render while the add-form is blocked", async () => {
    renderSection([line({ id: "p1", ...DISPLAY })], "заблокирано");

    expect(await screen.findByText(/Дисплей Samsung A52/)).toBeInTheDocument();
    expect(screen.getByText("заблокирано")).toBeInTheDocument();
  });
});

describe("PartLinesSection — Q5/Q5c one-click status suggestion", () => {
  it("shows a confirm/dismiss banner when adding a line returns a suggested_status", async () => {
    const user = userEvent.setup();
    vi.mocked(api.post).mockResolvedValue({ suggested_status: "waiting_parts" });
    renderSection([]);

    await screen.findByRole("option", { name: /Дисплей Samsung A52/ });
    await user.selectOptions(screen.getByRole("combobox"), "cat-1");
    await user.click(screen.getByRole("button", { name: "Поръчай" }));

    expect(await screen.findByText("Да премина ли в „Чака части“?")).toBeInTheDocument();
  });

  it("shows no banner when the response's suggested_status is null", async () => {
    const user = userEvent.setup();
    vi.mocked(api.post).mockResolvedValue({ suggested_status: null });
    renderSection([]);

    await screen.findByRole("option", { name: /Дисплей Samsung A52/ });
    await user.selectOptions(screen.getByRole("combobox"), "cat-1");
    await user.click(screen.getByRole("button", { name: "От наличност" }));

    expect(screen.queryByText(/Да премина ли/)).not.toBeInTheDocument();
  });

  it("confirming the suggestion posts the status change and clears the banner", async () => {
    const user = userEvent.setup();
    vi.mocked(api.patch).mockResolvedValue({ suggested_status: "repair" });
    vi.mocked(api.post).mockResolvedValue({});
    renderSection([line({ id: "p1", ...BATTERY, state: "ordered" })]);

    const select = await screen.findByRole("combobox", { name: /Батерия/ });
    await user.selectOptions(select, "Издадена");
    await screen.findByText("Да премина ли в „Ремонт“?");

    await user.click(screen.getByRole("button", { name: "Да" }));

    expect(api.post).toHaveBeenCalledWith("/orders/order-1/status", { to: "repair" });
    await waitFor(() => expect(screen.queryByText(/Да премина ли/)).not.toBeInTheDocument());
  });

  it("dismissing the suggestion just clears the banner without calling the status endpoint", async () => {
    const user = userEvent.setup();
    vi.mocked(api.post).mockResolvedValue({ suggested_status: "waiting_parts" });
    renderSection([]);

    await screen.findByRole("option", { name: /Дисплей Samsung A52/ });
    await user.selectOptions(screen.getByRole("combobox"), "cat-1");
    await user.click(screen.getByRole("button", { name: "Поръчай" }));
    await screen.findByText("Да премина ли в „Чака части“?");

    await user.click(screen.getByRole("button", { name: "Не" }));

    expect(screen.queryByText(/Да премина ли/)).not.toBeInTheDocument();
    expect(api.post).toHaveBeenCalledTimes(1); // only the original add, no status call
  });
});
