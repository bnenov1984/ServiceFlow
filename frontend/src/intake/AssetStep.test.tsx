import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../lib/api";
import { AssetStep, coerceFieldValue } from "./AssetStep";

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

function renderStep() {
  const onResolved = vi.fn();
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <AssetStep customerId={customerId} resolved={null} onResolved={onResolved}
                onChangeRequested={vi.fn()} />
    </QueryClientProvider>,
  );
  return { onResolved };
}

async function selectVehicleType(user: ReturnType<typeof userEvent.setup>) {
  await user.click(await screen.findByText("+ Нов актив"));
  await user.click(await screen.findByText("Автомобил"));
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
