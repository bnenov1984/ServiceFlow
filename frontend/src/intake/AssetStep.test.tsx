import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, api } from "../lib/api";
import {
  AssetStep, DEFAULT_ASSET_STEP_DRAFT, coerceFieldValue, type AssetStepDraft, type ResolvedAsset,
} from "./AssetStep";

vi.mock("../lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../lib/api")>();
  return { ...actual, api: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), put: vi.fn(), delete: vi.fn() } };
});

const customerId = "cust-1";

const vehicleType = {
  code: "vehicle", name_bg: "Автомобил", icon: "car",
  field_defs: [
    { key: "brand", label_bg: "Марка", type: "text" },
    { key: "model", label_bg: "Модел", type: "text" },
    { key: "reg_no", label_bg: "Рег. №", type: "text", identifier_kind: "reg" },
    { key: "vin", label_bg: "VIN", type: "text", identifier_kind: "vin" },
    { key: "year", label_bg: "Година", type: "number" },
    { key: "mileage", label_bg: "Пробег (км)", type: "number" },
  ],
};

beforeEach(() => {
  vi.mocked(api.get).mockReset();
  vi.mocked(api.post).mockReset();
  vi.mocked(api.get).mockImplementation((path: string) => {
    if (path === "/asset-types") return Promise.resolve([vehicleType]) as never;
    if (path.endsWith("/assets")) return Promise.resolve([]) as never;
    if (path.includes("/open-order")) {
      return Promise.resolve({ order_id: null, number: null, status_code: null }) as never;
    }
    return Promise.reject(new Error(`unexpected GET ${path}`));
  });
});

// Cleanup batch Issue 22: a small harness that owns the lifted draft state,
// the same shape IntakePage really uses (draft/onDraftChange), rather than
// AssetStep managing it internally — this is exactly what makes the
// draft-survives-unmount test below possible.
function Harness({
  onResolved, draft, onDraftChange,
}: {
  onResolved: (a: ResolvedAsset) => void;
  draft: AssetStepDraft;
  onDraftChange: (next: AssetStepDraft) => void;
}) {
  return (
    <AssetStep customerId={customerId} resolved={null} onResolved={onResolved}
              onChangeRequested={vi.fn()} draft={draft} onDraftChange={onDraftChange} />
  );
}

function renderStep() {
  const onResolved = vi.fn();
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });

  function Root() {
    const [draft, setDraft] = useState<AssetStepDraft>(DEFAULT_ASSET_STEP_DRAFT);
    return <Harness onResolved={onResolved} draft={draft} onDraftChange={setDraft} />;
  }

  render(
    <QueryClientProvider client={client}>
      <Root />
    </QueryClientProvider>,
  );
  return { onResolved };
}

// A harness that can unmount/remount AssetStep while keeping the SAME
// lifted draft alive in the parent — models "Customer step → Asset step →
// Back to Customer → Asset step again" (Issue 22) without needing the real
// IntakePage/CustomerStep wiring.
function renderToggleableStep() {
  const onResolved = vi.fn();
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });

  function Root() {
    const [draft, setDraft] = useState<AssetStepDraft>(DEFAULT_ASSET_STEP_DRAFT);
    const [showAssetStep, setShowAssetStep] = useState(true);
    return (
      <div>
        <button type="button" onClick={() => setShowAssetStep((v) => !v)}>
          toggle-asset-step
        </button>
        {showAssetStep && <Harness onResolved={onResolved} draft={draft} onDraftChange={setDraft} />}
      </div>
    );
  }

  render(
    <QueryClientProvider client={client}>
      <Root />
    </QueryClientProvider>,
  );
  return { onResolved };
}

// WP-C (Q18): every mock in this file returns exactly one asset type
// (`[vehicleType]`), matching the now-realistic "one type per business
// profile" shape — the picker grid auto-skips, so there is no "Автомобил"
// button to click any more, just the mode switch into "create".
async function selectVehicleType(user: ReturnType<typeof userEvent.setup>) {
  await user.click(await screen.findByText("+ Нов актив"));
}

// Issue 20's explicit escape hatch for a vehicle type that DOES carry a VIN
// field def — skips the VIN-first sub-form and lands on the full field form,
// with VIN left blank.
async function skipVin(user: ReturnType<typeof userEvent.setup>) {
  await user.click(await screen.findByRole("button", { name: "Продължи без VIN" }));
}

// FieldInput renders <label> and <input> as siblings inside a shared <div>,
// not associated via htmlFor/id or DOM nesting — getByLabelText can't
// resolve them (a pre-existing characteristic of the component, unrelated to
// the numeric-coercion bug this file tests; not something to fix here).
function inputForLabel(labelText: string): HTMLElement {
  const label = screen.getByText(labelText);
  const input = label.parentElement?.querySelector("input, select");
  if (!input) throw new Error(`no input found next to label "${labelText}"`);
  return input as HTMLElement;
}

describe("AssetStep numeric field coercion (form/schema boundary)", () => {
  it("sends 'Година'/'Пробег (км)' as real numbers, not strings", async () => {
    const user = userEvent.setup();
    vi.mocked(api.post).mockResolvedValue({
      id: "a1", label: "Toyota Corolla", asset_type_code: "vehicle",
      archived: false, duplicate_asset_ids: [],
    });
    renderStep();

    await selectVehicleType(user);
    await skipVin(user);
    await user.type(inputForLabel("Година"), "2015");
    await user.type(inputForLabel("Пробег (км)"), "100000");
    await user.click(screen.getByRole("button", { name: "Продължи" }));

    expect(api.post).toHaveBeenCalledWith(`/customers/${customerId}/assets`, {
      asset_type_code: "vehicle",
      field_values: expect.objectContaining({ year: 2015, mileage: 100000 }),
    });
    const [, body] = vi.mocked(api.post).mock.calls[0] as [string, { field_values: Record<string, unknown> }];
    expect(typeof body.field_values.year).toBe("number");
    expect(typeof body.field_values.mileage).toBe("number");
  });

  it("still omits empty optional numeric fields from the payload", async () => {
    const user = userEvent.setup();
    vi.mocked(api.post).mockResolvedValue({
      id: "a1", label: "Toyota Corolla", asset_type_code: "vehicle",
      archived: false, duplicate_asset_ids: [],
    });
    renderStep();

    await selectVehicleType(user);
    await skipVin(user);
    await user.type(inputForLabel("Марка"), "Toyota");
    // Година/Пробег (км) left empty.
    await user.click(screen.getByRole("button", { name: "Продължи" }));

    const [, body] = vi.mocked(api.post).mock.calls[0] as [string, { field_values: Record<string, unknown> }];
    expect(body.field_values).not.toHaveProperty("year");
    expect(body.field_values).not.toHaveProperty("mileage");
  });

  it("leaves text-type fields as strings, untouched by number coercion", async () => {
    const user = userEvent.setup();
    vi.mocked(api.post).mockResolvedValue({
      id: "a1", label: "Toyota Corolla", asset_type_code: "vehicle",
      archived: false, duplicate_asset_ids: [],
    });
    renderStep();

    await selectVehicleType(user);
    await skipVin(user);
    await user.type(inputForLabel("Марка"), "Toyota");
    await user.click(screen.getByRole("button", { name: "Продължи" }));

    const [, body] = vi.mocked(api.post).mock.calls[0] as [string, { field_values: Record<string, unknown> }];
    expect(body.field_values.brand).toBe("Toyota");
  });
});

describe("AssetStep choice-type field (Issue 23: automotive make dropdown)", () => {
  const vehicleTypeWithChoiceBrand = {
    code: "vehicle", name_bg: "Автомобил", icon: "car",
    field_defs: [
      { key: "brand", label_bg: "Марка", type: "choice",
        choices: ["Audi", "Volkswagen", "Друго"] },
      { key: "model", label_bg: "Модел", type: "text" },
    ],
  };

  it("renders the brand field as a select limited to the given choices, not free text", async () => {
    const user = userEvent.setup();
    vi.mocked(api.get).mockReset();
    vi.mocked(api.get).mockImplementation((path: string) => {
      if (path === "/asset-types") return Promise.resolve([vehicleTypeWithChoiceBrand]) as never;
      if (path.endsWith("/assets")) return Promise.resolve([]) as never;
    if (path.includes("/open-order")) {
      return Promise.resolve({ order_id: null, number: null, status_code: null }) as never;
    }
      return Promise.reject(new Error(`unexpected GET ${path}`));
    });
    vi.mocked(api.post).mockResolvedValue({
      id: "a1", label: "Volkswagen Golf", asset_type_code: "vehicle",
      archived: false, duplicate_asset_ids: [],
    });
    renderStep();

    // No "vin" field_def on this type — the VIN-first sub-step is skipped
    // automatically, straight to the full field form (see AssetStep's
    // `showVinFirst && vinDef` render gate).
    await selectVehicleType(user);
    const brandSelect = inputForLabel("Марка");
    expect(brandSelect.tagName).toBe("SELECT");
    await user.selectOptions(brandSelect, "Volkswagen");
    await user.type(inputForLabel("Модел"), "Golf");
    await user.click(screen.getByRole("button", { name: "Продължи" }));

    expect(api.post).toHaveBeenCalledWith(`/customers/${customerId}/assets`, {
      asset_type_code: "vehicle",
      field_values: { brand: "Volkswagen", model: "Golf" },
    });
  });
});

describe("AssetStep back navigation", () => {
  it("lets the user cancel out of the type picker back to the asset list", async () => {
    // The picker grid itself only renders for a company that still has more
    // than one type (WP-C: real cross-type history migration 0034 couldn't
    // safely collapse) — every other test in this file has exactly one.
    const otherType = {
      code: "other", name_bg: "Друго", icon: "wrench",
      field_defs: [{ key: "description", label_bg: "Описание", type: "text" }],
    };
    vi.mocked(api.get).mockImplementation((path: string) => {
      if (path === "/asset-types") return Promise.resolve([vehicleType, otherType]) as never;
      if (path.endsWith("/assets")) return Promise.resolve([]) as never;
    if (path.includes("/open-order")) {
      return Promise.resolve({ order_id: null, number: null, status_code: null }) as never;
    }
      return Promise.reject(new Error(`unexpected GET ${path}`));
    });
    const user = userEvent.setup();
    renderStep();

    await user.click(await screen.findByText("+ Нов актив"));
    expect(await screen.findByRole("button", { name: "Автомобил" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Отказ" }));

    expect(screen.getByText("+ Нов актив")).toBeInTheDocument();
    expect(screen.queryByText("Автомобил")).not.toBeInTheDocument();
  });
});

describe("AssetStep — WP-C Q18 (single-type companies skip the picker)", () => {
  it("goes straight to the vehicle form when the company has exactly one asset type", async () => {
    const user = userEvent.setup();
    renderStep();

    await user.click(await screen.findByText("+ Нов актив"));

    expect(screen.queryByRole("button", { name: "Автомобил" })).not.toBeInTheDocument();
    // vehicleType carries a "vin" field_def, so the VIN-first sub-form is
    // what a direct, auto-selected landing looks like.
    expect(await screen.findByRole("button", { name: "Провери VIN" })).toBeInTheDocument();
  });
});

describe("AssetStep — WP-H (Q16/Q16b: accessories flag carried onto the resolved asset)", () => {
  it("resolves with accessories: false for a vehicle (automotive has it off)", async () => {
    const user = userEvent.setup();
    vi.mocked(api.get).mockImplementation((path: string) => {
      if (path === "/asset-types") {
        return Promise.resolve([{ ...vehicleType, accessories: false }]) as never;
      }
      if (path.endsWith("/assets")) {
        return Promise.resolve([
          { id: "a1", label: "Volkswagen Golf", asset_type_code: "vehicle", archived: false },
        ]) as never;
      }
      if (path.includes("/open-order")) {
        return Promise.resolve({ order_id: null, number: null, status_code: null }) as never;
      }
      return Promise.reject(new Error(`unexpected GET ${path}`));
    });
    const { onResolved } = renderStep();

    await user.click(await screen.findByText("Volkswagen Golf"));

    expect(onResolved).toHaveBeenCalledWith({
      id: "a1", label: "Volkswagen Golf", assetTypeCode: "vehicle", accessories: false,
    });
  });

  it("resolves with accessories: true for a type that carries the flag as true", async () => {
    const user = userEvent.setup();
    vi.mocked(api.get).mockImplementation((path: string) => {
      if (path === "/asset-types") {
        return Promise.resolve([{ ...vehicleType, code: "phone", accessories: true }]) as never;
      }
      if (path.endsWith("/assets")) {
        return Promise.resolve([
          { id: "a2", label: "iPhone 12", asset_type_code: "phone", archived: false },
        ]) as never;
      }
      if (path.includes("/open-order")) {
        return Promise.resolve({ order_id: null, number: null, status_code: null }) as never;
      }
      return Promise.reject(new Error(`unexpected GET ${path}`));
    });
    const { onResolved } = renderStep();

    await user.click(await screen.findByText("iPhone 12"));

    expect(onResolved).toHaveBeenCalledWith({
      id: "a2", label: "iPhone 12", assetTypeCode: "phone", accessories: true,
    });
  });
});

describe("AssetStep VIN-first lookup (Issue 20: VIN before the full form)", () => {
  const customerId2 = "cust-2";

  function mockByVin(impl: (vin: string) => unknown) {
    vi.mocked(api.get).mockImplementation((path: string) => {
      if (path === "/asset-types") return Promise.resolve([vehicleType]) as never;
      if (path.endsWith("/assets")) return Promise.resolve([]) as never;
    if (path.includes("/open-order")) {
      return Promise.resolve({ order_id: null, number: null, status_code: null }) as never;
    }
      if (path.startsWith("/assets/by-vin")) {
        const vin = decodeURIComponent(path.split("vin=")[1] ?? "");
        const result = impl(vin);
        if (result === null) {
          return Promise.reject(new ApiError(404, "not_found", "errors.assets.vin_not_found")) as never;
        }
        return Promise.resolve(result) as never;
      }
      return Promise.reject(new Error(`unexpected GET ${path}`));
    });
  }

  it("selecting the vehicle type shows a VIN-only sub-form first, not the full field form", async () => {
    const user = userEvent.setup();
    mockByVin(() => null);
    renderStep();

    await selectVehicleType(user);

    expect(inputForLabel("VIN")).toBeInTheDocument();
    expect(screen.queryByText("Марка")).not.toBeInTheDocument();
    expect(screen.queryByText("Модел")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Провери VIN" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Продължи без VIN" })).toBeInTheDocument();
  });

  it("checking a VIN with no match proceeds to the full form with the VIN retained", async () => {
    const user = userEvent.setup();
    mockByVin(() => null);
    vi.mocked(api.post).mockResolvedValue({
      id: "a1", label: "Volkswagen Golf", asset_type_code: "vehicle",
      archived: false, duplicate_asset_ids: [],
    });
    renderStep();

    await selectVehicleType(user);
    await user.type(inputForLabel("VIN"), "WVWZZZ1JZ3W386752");
    await user.click(screen.getByRole("button", { name: "Провери VIN" }));

    expect(api.get).toHaveBeenCalledWith("/assets/by-vin?vin=WVWZZZ1JZ3W386752");
    // Now on the full form — Марка/Модел are visible, and VIN kept its value.
    expect(await screen.findByText("Марка")).toBeInTheDocument();
    expect(inputForLabel("VIN")).toHaveValue("WVWZZZ1JZ3W386752");

    await user.click(screen.getByRole("button", { name: "Продължи" }));

    expect(api.post).toHaveBeenCalledWith(`/customers/${customerId}/assets`, {
      asset_type_code: "vehicle",
      field_values: expect.objectContaining({ vin: "WVWZZZ1JZ3W386752" }),
    });
  });

  it('"Продължи без VIN" skips the lookup entirely and proceeds to the full form', async () => {
    const user = userEvent.setup();
    mockByVin(() => null);
    renderStep();

    await selectVehicleType(user);
    await skipVin(user);

    expect(await screen.findByText("Марка")).toBeInTheDocument();
    expect(api.get).not.toHaveBeenCalledWith(expect.stringContaining("/assets/by-vin"));
  });

  it("reuses the vehicle outright when the VIN already belongs to this customer, without posting a create", async () => {
    const user = userEvent.setup();
    mockByVin(() => ({
      id: "existing-1", label: "Volkswagen Golf", asset_type_code: "vehicle",
      customer_id: customerId, customer_name: "Иван Иванов",
    }));
    const { onResolved } = renderStep();

    await selectVehicleType(user);
    await user.type(inputForLabel("VIN"), "WVWZZZ1JZ3W386752");
    await user.click(screen.getByRole("button", { name: "Провери VIN" }));

    expect(onResolved).toHaveBeenCalledWith({
      id: "existing-1", label: "Volkswagen Golf", assetTypeCode: "vehicle", accessories: true,
    });
    expect(api.post).not.toHaveBeenCalled();
  });

  it("shows the owner-conflict choice when the VIN belongs to a different customer", async () => {
    const user = userEvent.setup();
    mockByVin(() => ({
      id: "existing-2", label: "Volkswagen Golf", asset_type_code: "vehicle",
      customer_id: customerId2, customer_name: "Петър Петров",
    }));
    renderStep();

    await selectVehicleType(user);
    await user.type(inputForLabel("VIN"), "WVWZZZ1JZ3W386752");
    await user.click(screen.getByRole("button", { name: "Провери VIN" }));

    expect(await screen.findByText(
      "Автомобилът вече съществува и е свързан с Петър Петров.",
    )).toBeInTheDocument();
    expect(api.post).not.toHaveBeenCalled();
  });

  it('"Използвай автомобила" resolves with the existing asset and never calls transfer-owner', async () => {
    const user = userEvent.setup();
    mockByVin(() => ({
      id: "existing-2", label: "Volkswagen Golf", asset_type_code: "vehicle",
      customer_id: customerId2, customer_name: "Петър Петров",
    }));
    const { onResolved } = renderStep();

    await selectVehicleType(user);
    await user.type(inputForLabel("VIN"), "WVWZZZ1JZ3W386752");
    await user.click(screen.getByRole("button", { name: "Провери VIN" }));
    await user.click(await screen.findByRole("button", { name: "Използвай автомобила" }));

    expect(onResolved).toHaveBeenCalledWith({
      id: "existing-2", label: "Volkswagen Golf", assetTypeCode: "vehicle", accessories: true,
    });
    expect(api.post).not.toHaveBeenCalled();
  });

  it('"Смени собственик" calls transfer-owner and resolves with the (now-transferred) asset', async () => {
    const user = userEvent.setup();
    mockByVin(() => ({
      id: "existing-2", label: "Volkswagen Golf", asset_type_code: "vehicle",
      customer_id: customerId2, customer_name: "Петър Петров",
    }));
    vi.mocked(api.post).mockResolvedValue({
      id: "existing-2", customer_id: customerId, asset_type_code: "vehicle",
      label: "Volkswagen Golf", field_values: {}, archived: false, row_version: 2,
      duplicate_asset_ids: [],
    });
    const { onResolved } = renderStep();

    await selectVehicleType(user);
    await user.type(inputForLabel("VIN"), "WVWZZZ1JZ3W386752");
    await user.click(screen.getByRole("button", { name: "Провери VIN" }));
    await user.click(await screen.findByRole("button", { name: "Смени собственик" }));

    expect(api.post).toHaveBeenCalledWith("/assets/existing-2/transfer-owner", {
      customer_id: customerId,
    });
    expect(onResolved).toHaveBeenCalledWith({
      id: "existing-2", label: "Volkswagen Golf", assetTypeCode: "vehicle", accessories: true,
    });
  });
});

describe("AssetStep draft survives navigation (cleanup batch Issue 22)", () => {
  it("keeps unsaved full-form field values after the step unmounts and remounts with the same lifted draft", async () => {
    const user = userEvent.setup();
    mockByVinNoMatch();
    renderToggleableStep();

    await selectVehicleType(user);
    await skipVin(user);
    await user.type(inputForLabel("Марка"), "Toyota");
    await user.type(inputForLabel("Модел"), "Corolla");

    // Simulate "Back to Customer step" (AssetStep unmounts) then "forward to
    // Asset step again" (remounts) — the parent's lifted draft is untouched
    // by either toggle, exactly like IntakePage's own customer/asset
    // conditional rendering.
    await user.click(screen.getByRole("button", { name: "toggle-asset-step" }));
    await user.click(screen.getByRole("button", { name: "toggle-asset-step" }));

    expect(await screen.findByText("Марка")).toBeInTheDocument();
    expect(inputForLabel("Марка")).toHaveValue("Toyota");
    expect(inputForLabel("Модел")).toHaveValue("Corolla");
  });

  it("keeps the VIN-first phase (not yet checked) after unmount/remount", async () => {
    const user = userEvent.setup();
    mockByVinNoMatch();
    renderToggleableStep();

    await selectVehicleType(user);
    await user.type(inputForLabel("VIN"), "WVWZZZ1JZ3W386752");

    await user.click(screen.getByRole("button", { name: "toggle-asset-step" }));
    await user.click(screen.getByRole("button", { name: "toggle-asset-step" }));

    // Still on the VIN-first sub-form (never checked), with the typed VIN retained.
    expect(await screen.findByRole("button", { name: "Провери VIN" })).toBeInTheDocument();
    expect(inputForLabel("VIN")).toHaveValue("WVWZZZ1JZ3W386752");
  });

  function mockByVinNoMatch() {
    vi.mocked(api.get).mockImplementation((path: string) => {
      if (path === "/asset-types") return Promise.resolve([vehicleType]) as never;
      if (path.endsWith("/assets")) return Promise.resolve([]) as never;
    if (path.includes("/open-order")) {
      return Promise.resolve({ order_id: null, number: null, status_code: null }) as never;
    }
      if (path.startsWith("/assets/by-vin")) {
        return Promise.reject(new ApiError(404, "not_found", "errors.assets.vin_not_found")) as never;
      }
      return Promise.reject(new Error(`unexpected GET ${path}`));
    });
  }
});

// A harness that actually threads `onResolved` back into `resolved` (every
// other harness in this file hard-codes resolved={null}) — needed to reach
// the post-resolution vehicle-history render. Wrapped in MemoryRouter since
// VehicleVisitList renders react-router <Link>s.
function renderStepWithResolution() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });

  function Root() {
    const [draft, setDraft] = useState<AssetStepDraft>(DEFAULT_ASSET_STEP_DRAFT);
    const [resolved, setResolved] = useState<ResolvedAsset | null>(null);
    return (
      <AssetStep
        customerId={customerId} resolved={resolved} onResolved={setResolved}
        onChangeRequested={() => setResolved(null)} draft={draft} onDraftChange={setDraft}
      />
    );
  }

  render(
    <MemoryRouter>
      <QueryClientProvider client={client}>
        <Root />
      </QueryClientProvider>
    </MemoryRouter>,
  );
}

describe("AssetStep — Q6b (open-order block at the asset step)", () => {
  function mockWithOpenOrder(
    openOrder: { order_id: string | null; number: string | null; status_code: string | null },
  ) {
    vi.mocked(api.get).mockImplementation((path: string) => {
      if (path === "/asset-types") return Promise.resolve([vehicleType]) as never;
      if (path.endsWith("/assets")) {
        return Promise.resolve([
          { id: "existing-9", label: "Volkswagen Golf", asset_type_code: "vehicle", archived: false },
        ]) as never;
      }
      if (path.includes("/open-order")) return Promise.resolve(openOrder) as never;
      return Promise.reject(new Error(`unexpected GET ${path}`));
    });
  }

  it("blocks with a link to the open order instead of resolving", async () => {
    const user = userEvent.setup();
    mockWithOpenOrder({ order_id: "order-5", number: "2026-00005", status_code: "repair" });
    renderStepWithResolution();

    await user.click(await screen.findByText("Volkswagen Golf"));

    expect(await screen.findByText(
      "Има отворена поръчка №2026-00005 (Ремонт) за този актив.",
    )).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Отвори я" })).toHaveAttribute("href", "/orders/order-5");
  });

  it('"Промени" clears the block, returning to the pick list', async () => {
    const user = userEvent.setup();
    mockWithOpenOrder({ order_id: "order-5", number: "2026-00005", status_code: "repair" });
    renderStepWithResolution();

    await user.click(await screen.findByText("Volkswagen Golf"));
    await screen.findByText(/Има отворена поръчка/);
    await user.click(screen.getByRole("button", { name: "Промени" }));

    expect(await screen.findByText("Volkswagen Golf")).toBeInTheDocument();
  });

  it("resolves normally when the asset has no open order", async () => {
    const user = userEvent.setup();
    mockWithOpenOrder({ order_id: null, number: null, status_code: null });
    renderStepWithResolution();

    await user.click(await screen.findByText("Volkswagen Golf"));

    expect(screen.queryByText(/Има отворена поръчка/)).not.toBeInTheDocument();
    // The resolved confirmation box's own "change" link, proving we landed
    // on the normal resolved view, not stuck mid-pick.
    expect(await screen.findByText("Промени")).toBeInTheDocument();
  });
});

describe("AssetStep — Q11 (reg-№ on-blur conflict check)", () => {
  function mockRegCheck(impl: (reg: string) => { asset_id: string | null; label: string | null }) {
    vi.mocked(api.get).mockImplementation((path: string) => {
      if (path === "/asset-types") return Promise.resolve([vehicleType]) as never;
      if (path.endsWith("/assets")) return Promise.resolve([]) as never;
    if (path.includes("/open-order")) {
      return Promise.resolve({ order_id: null, number: null, status_code: null }) as never;
    }
      if (path.startsWith("/assets/by-vin")) {
        return Promise.reject(new ApiError(404, "not_found", "errors.assets.vin_not_found")) as never;
      }
      if (path.startsWith("/assets/reg-check")) {
        const reg = decodeURIComponent(path.split("reg=")[1] ?? "");
        return Promise.resolve(impl(reg)) as never;
      }
      return Promise.reject(new Error(`unexpected GET ${path}`));
    });
  }

  it("shows an inline conflict with a resolve action when reg-№ matches an existing vehicle on blur", async () => {
    const user = userEvent.setup();
    mockRegCheck(() => ({ asset_id: "existing-3", label: "Volkswagen Golf" }));
    const { onResolved } = renderStep();

    await selectVehicleType(user);
    await skipVin(user);
    await user.type(inputForLabel("Рег. №"), "CA5070BA");
    await user.tab();

    expect(await screen.findByText("Този рег. № вече принадлежи на друг актив."))
      .toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Използвай автомобила" }));

    expect(onResolved).toHaveBeenCalledWith({
      id: "existing-3", label: "Volkswagen Golf", assetTypeCode: "vehicle", accessories: true,
    });
  });

  it("shows no conflict when reg-№ has no match", async () => {
    const user = userEvent.setup();
    mockRegCheck(() => ({ asset_id: null, label: null }));
    renderStep();

    await selectVehicleType(user);
    await skipVin(user);
    await user.type(inputForLabel("Рег. №"), "CA5070BA");
    await user.tab();

    await waitFor(() => expect(api.get).toHaveBeenCalledWith(
      expect.stringContaining("/assets/reg-check"),
    ));
    expect(screen.queryByText("Този рег. № вече принадлежи на друг актив.")).not.toBeInTheDocument();
  });

  it("clears a stale conflict as soon as the reg-№ value is edited again", async () => {
    const user = userEvent.setup();
    mockRegCheck(() => ({ asset_id: "existing-3", label: "Volkswagen Golf" }));
    renderStep();

    await selectVehicleType(user);
    await skipVin(user);
    const regInput = inputForLabel("Рег. №");
    await user.type(regInput, "CA5070BA");
    await user.tab();
    expect(await screen.findByText("Този рег. № вече принадлежи на друг актив."))
      .toBeInTheDocument();

    await user.click(regInput);
    await user.type(regInput, "X");

    expect(screen.queryByText("Този рег. № вече принадлежи на друг актив.")).not.toBeInTheDocument();
  });
});

describe("AssetStep — #20 (vehicle history at intake)", () => {
  function mockWithServiceHistory(
    visits: Array<{
      order_id: string; order_number: string; created_at: string; status_code: string;
      customer_id: string; customer_name: string; complaint: string; mileage: number | null;
    }>,
  ) {
    vi.mocked(api.get).mockImplementation((path: string) => {
      if (path === "/asset-types") return Promise.resolve([vehicleType]) as never;
      if (path.endsWith("/assets")) return Promise.resolve([]) as never;
    if (path.includes("/open-order")) {
      return Promise.resolve({ order_id: null, number: null, status_code: null }) as never;
    }
      if (path.startsWith("/assets/by-vin")) {
        return Promise.reject(new ApiError(404, "not_found", "errors.assets.vin_not_found")) as never;
      }
      if (path.includes("/service-history")) return Promise.resolve({ visits }) as never;
      return Promise.reject(new Error(`unexpected GET ${path}`));
    });
  }

  it("shows prior visits once a freshly-created vehicle asset is resolved", async () => {
    const user = userEvent.setup();
    mockWithServiceHistory([{
      order_id: "o1", order_number: "2026-00005", created_at: "2026-01-01T00:00:00Z",
      status_code: "ready", customer_id: "c1", customer_name: "Иван", complaint: "Спирачки",
      mileage: 50000,
    }]);
    vi.mocked(api.post).mockResolvedValue({
      id: "a1", label: "Volkswagen Golf", asset_type_code: "vehicle",
      archived: false, duplicate_asset_ids: [],
    });
    renderStepWithResolution();

    await selectVehicleType(user);
    await skipVin(user);
    await user.type(inputForLabel("Марка"), "Volkswagen");
    await user.click(screen.getByRole("button", { name: "Продължи" }));

    expect(await screen.findByText("2026-00005")).toBeInTheDocument();
    expect(screen.getByText(/Спирачки/)).toBeInTheDocument();
  });

  it("shows the empty-history message for a vehicle with no prior visits", async () => {
    const user = userEvent.setup();
    mockWithServiceHistory([]);
    vi.mocked(api.post).mockResolvedValue({
      id: "a1", label: "Volkswagen Golf", asset_type_code: "vehicle",
      archived: false, duplicate_asset_ids: [],
    });
    renderStepWithResolution();

    await selectVehicleType(user);
    await skipVin(user);
    await user.type(inputForLabel("Марка"), "Volkswagen");
    await user.click(screen.getByRole("button", { name: "Продължи" }));

    expect(await screen.findByText("Няма предишна история за този автомобил.")).toBeInTheDocument();
  });
});

describe("coerceFieldValue", () => {
  const yearDef = { key: "year", label_bg: "Година", type: "number" as const };
  const brandDef = { key: "brand", label_bg: "Марка", type: "text" as const };

  it("converts a valid numeric string to a number for a number field", () => {
    expect(coerceFieldValue(yearDef, "2015")).toBe(2015);
    expect(coerceFieldValue(yearDef, "100000")).toBe(100000);
  });

  it("leaves non-number field types as the original string", () => {
    expect(coerceFieldValue(brandDef, "Toyota")).toBe("Toyota");
  });

  it("fails closed on unparseable input for a number field — never silently null", () => {
    // Must stay the original string so the backend's own isinstance(raw, int | float)
    // check still rejects it as not_a_number, rather than JSON.stringify(NaN) → null
    // being treated as "absent" and skipping validation entirely.
    const result = coerceFieldValue(yearDef, "abc");
    expect(result).toBe("abc");
    expect(Number.isNaN(result)).toBe(false);
  });
});
