import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
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

async function selectVehicleType(user: ReturnType<typeof userEvent.setup>) {
  await user.click(await screen.findByText("+ Нов актив"));
  await user.click(await screen.findByText("Автомобил"));
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
    const user = userEvent.setup();
    renderStep();

    await user.click(await screen.findByText("+ Нов актив"));
    expect(await screen.findByText("Автомобил")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Отказ" }));

    expect(screen.getByText("+ Нов актив")).toBeInTheDocument();
    expect(screen.queryByText("Автомобил")).not.toBeInTheDocument();
  });
});

describe("AssetStep VIN-first lookup (Issue 20: VIN before the full form)", () => {
  const customerId2 = "cust-2";

  function mockByVin(impl: (vin: string) => unknown) {
    vi.mocked(api.get).mockImplementation((path: string) => {
      if (path === "/asset-types") return Promise.resolve([vehicleType]) as never;
      if (path.endsWith("/assets")) return Promise.resolve([]) as never;
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
      id: "existing-1", label: "Volkswagen Golf", assetTypeCode: "vehicle",
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
      id: "existing-2", label: "Volkswagen Golf", assetTypeCode: "vehicle",
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
      id: "existing-2", label: "Volkswagen Golf", assetTypeCode: "vehicle",
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
      if (path.startsWith("/assets/by-vin")) {
        return Promise.reject(new ApiError(404, "not_found", "errors.assets.vin_not_found")) as never;
      }
      return Promise.reject(new Error(`unexpected GET ${path}`));
    });
  }
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
