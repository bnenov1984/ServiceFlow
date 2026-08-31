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
  priority: "normal", technicianId: null,
};

// A real controlled wrapper (useState, not a mock) so add/remove actions
// actually re-render OrderStep with the updated draft, the same way
// IntakePage drives it for real.
function Harness({ initial = DEFAULT_VALUE }: { initial?: OrderStepValue }) {
  const [value, setValue] = useState(initial);
  return (
    <OrderStep
      value={value}
      onChange={setValue}
      onSubmit={vi.fn()}
      submitting={false}
      error={null}
    />
  );
}

function renderStep(initial?: OrderStepValue) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <Harness initial={initial} />
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
