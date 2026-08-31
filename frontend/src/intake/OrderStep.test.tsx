import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";
import { OrderStep, type OrderStepValue } from "./OrderStep";

vi.mock("../lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../lib/api")>();
  return { ...actual, api: { ...actual.api, get: vi.fn().mockResolvedValue([]) } };
});

const DEFAULT_VALUE: OrderStepValue = {
  complaint: "", accessories: [], photos: [], partLines: [],
  priority: "normal", technicianId: null, mileage: "",
  deliveryMethod: "pickup", deliveryAddress: "",
};

// A real controlled wrapper (useState, not a mock) so add/remove actions
// actually re-render OrderStep with the updated draft, the same way
// IntakePage drives it for real.
function Harness({
  initial = DEFAULT_VALUE, assetTypeCode = "phone", defaultDeliveryAddress = null,
}: {
  initial?: OrderStepValue; assetTypeCode?: string; defaultDeliveryAddress?: string | null;
}) {
  const [value, setValue] = useState(initial);
  return (
    <OrderStep
      value={value}
      assetTypeCode={assetTypeCode}
      defaultDeliveryAddress={defaultDeliveryAddress}
      onChange={setValue}
      onSubmit={vi.fn()}
      submitting={false}
      error={null}
    />
  );
}

function renderStep(
  initial?: OrderStepValue, assetTypeCode?: string, defaultDeliveryAddress?: string | null,
) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <Harness
        initial={initial} assetTypeCode={assetTypeCode}
        defaultDeliveryAddress={defaultDeliveryAddress}
      />
    </QueryClientProvider>,
  );
  // The "Добави" accessible name is reused by AccessoriesChecklist's own add
  // button on this same screen — scope every query to the parts section's
  // own container so the two never collide.
  return within(screen.getByText("Части (по избор)").closest("div") as HTMLElement);
}

describe("OrderStep — Issue 25 (no promised date at intake)", () => {
  it("does not render a promised-date field any more", () => {
    renderStep();
    expect(screen.queryByText("Обещана дата")).not.toBeInTheDocument();
  });
});

describe("OrderStep — Wave 3 Issues 21/26/27 (mileage at intake)", () => {
  it("shows the mileage field for a vehicle order", () => {
    renderStep(undefined, "vehicle");
    expect(screen.getByText("Пробег (км)")).toBeInTheDocument();
  });

  it("does not show the mileage field for a non-vehicle order", () => {
    renderStep(undefined, "phone");
    expect(screen.queryByText("Пробег (км)")).not.toBeInTheDocument();
  });

  it("typing a mileage value updates the draft", async () => {
    const user = userEvent.setup();
    renderStep(undefined, "vehicle");

    const input = screen.getByText("Пробег (км)").parentElement
      ?.querySelector("input") as HTMLInputElement;
    await user.type(input, "123000");

    expect(input).toHaveValue(123000);
  });
});

describe("OrderStep — Wave 5 Issue 12 (order delivery method/address)", () => {
  it("defaults to pickup, with no delivery-address field shown", () => {
    renderStep();
    expect(screen.getByRole("button", { name: "Взимане от сервиза" }))
      .toHaveAttribute("aria-pressed", "true");
    expect(screen.queryByLabelText("Адрес за доставка")).not.toBeInTheDocument();
  });

  it("shows the delivery-address field only once courier is chosen", async () => {
    const user = userEvent.setup();
    renderStep();

    await user.click(screen.getByRole("button", { name: "Куриер" }));

    expect(screen.getByLabelText("Адрес за доставка")).toBeInTheDocument();
  });

  it("prefills the delivery address from the customer's default once courier is chosen", async () => {
    const user = userEvent.setup();
    renderStep(undefined, "phone", "ул. Тестова 5");

    await user.click(screen.getByRole("button", { name: "Куриер" }));

    expect(screen.getByLabelText("Адрес за доставка")).toHaveValue("ул. Тестова 5");
  });

  it("never overwrites an address the user already typed", async () => {
    const user = userEvent.setup();
    renderStep(undefined, "phone", "адрес по подразбиране");

    await user.click(screen.getByRole("button", { name: "Куриер" }));
    const input = screen.getByLabelText("Адрес за доставка");
    await user.clear(input);
    await user.type(input, "ръчно въведен адрес");
    await user.click(screen.getByRole("button", { name: "Взимане от сервиза" }));
    await user.click(screen.getByRole("button", { name: "Куриер" }));

    expect(screen.getByLabelText("Адрес за доставка")).toHaveValue("ръчно въведен адрес");
  });
});

describe("OrderStep — Issue 29 (parts addable at intake)", () => {
  it("shows the parts section with an empty-state message by default", () => {
    const parts = renderStep();
    expect(parts.getByText("Няма добавени части.")).toBeInTheDocument();
  });

  it("adding a part line shows it in the list with name and price", async () => {
    const user = userEvent.setup();
    const parts = renderStep();

    await user.type(parts.getByPlaceholderText("Име на частта…"), "Дисплей");
    await user.type(parts.getByPlaceholderText("€"), "85");
    await user.click(parts.getByRole("button", { name: "Добави" }));

    expect(parts.getByText("Дисплей · 85.00 €")).toBeInTheDocument();
    expect(parts.queryByText("Няма добавени части.")).not.toBeInTheDocument();
  });

  it("clears the name/price inputs after adding", async () => {
    const user = userEvent.setup();
    const parts = renderStep();

    await user.type(parts.getByPlaceholderText("Име на частта…"), "Дисплей");
    await user.type(parts.getByPlaceholderText("€"), "85");
    await user.click(parts.getByRole("button", { name: "Добави" }));

    expect(parts.getByPlaceholderText("Име на частта…")).toHaveValue("");
    expect(parts.getByPlaceholderText("€")).toHaveValue(null);
  });

  it("added part lines render pre-seeded, and can be removed", async () => {
    const user = userEvent.setup();
    const parts = renderStep({ ...DEFAULT_VALUE, partLines: [{ name: "Батерия", unitPrice: 32 }] });

    expect(parts.getByText("Батерия · 32.00 €")).toBeInTheDocument();
    await user.click(parts.getByLabelText("Затвори"));
    expect(parts.queryByText("Батерия · 32.00 €")).not.toBeInTheDocument();
    expect(parts.getByText("Няма добавени части.")).toBeInTheDocument();
  });

  it("does not add an empty-name part line", async () => {
    const user = userEvent.setup();
    const parts = renderStep();

    await user.type(parts.getByPlaceholderText("€"), "10");
    await user.click(parts.getByRole("button", { name: "Добави" }));

    expect(parts.getByText("Няма добавени части.")).toBeInTheDocument();
  });

  it("defaults an omitted price to 0", async () => {
    const user = userEvent.setup();
    const parts = renderStep();

    await user.type(parts.getByPlaceholderText("Име на частта…"), "Винт");
    await user.click(parts.getByRole("button", { name: "Добави" }));

    expect(parts.getByText("Винт · 0.00 €")).toBeInTheDocument();
  });
});
