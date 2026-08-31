import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { DeliveryDialog } from "./DeliveryDialog";

const noop = () => {};

describe("DeliveryDialog", () => {
  it("renders the payment entry fields (amount, method, note)", () => {
    render(
      <DeliveryDialog
        open
        onClose={noop}
        onConfirm={vi.fn()}
        accessories={[]}
        onToggleReturned={noop}
        submitting={false}
        error={null}
        orderWarrantyDays={null}
        laborWarrantyDefault={null}
      />,
    );

    expect(screen.getByPlaceholderText("Сума (€)")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "В брой" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Карта" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Банков превод" })).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Бележка…")).toBeInTheDocument();
  });

  it("submits a payment alongside delivery when an amount is entered", async () => {
    const user = userEvent.setup();
    const onConfirm = vi.fn();
    render(
      <DeliveryDialog
        open
        onClose={noop}
        onConfirm={onConfirm}
        accessories={[]}
        onToggleReturned={noop}
        submitting={false}
        error={null}
        orderWarrantyDays={null}
        laborWarrantyDefault={null}
      />,
    );

    await user.type(screen.getByPlaceholderText("Сума (€)"), "50");
    await user.click(screen.getByRole("button", { name: "Карта" }));
    await user.type(screen.getByPlaceholderText("Бележка…"), "депозит");
    await user.click(screen.getByRole("button", { name: "Предай" }));

    expect(onConfirm).toHaveBeenCalledWith(null, {
      amount: 50, method: "card", note: "депозит",
    });
  });

  it("allows delivery with no payment entered — an open balance never blocks it", async () => {
    const user = userEvent.setup();
    const onConfirm = vi.fn();
    render(
      <DeliveryDialog
        open
        onClose={noop}
        onConfirm={onConfirm}
        accessories={[]}
        onToggleReturned={noop}
        submitting={false}
        error={null}
        orderWarrantyDays={null}
        laborWarrantyDefault={null}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Предай" }));

    expect(onConfirm).toHaveBeenCalledWith(null, null);
  });

  it("renders a backend error by its translated message_key text", () => {
    render(
      <DeliveryDialog
        open
        onClose={noop}
        onConfirm={vi.fn()}
        accessories={[]}
        onToggleReturned={noop}
        submitting={false}
        error="Поръчката е архивирана."
        orderWarrantyDays={null}
        laborWarrantyDefault={null}
      />,
    );

    expect(screen.getByRole("alert")).toHaveTextContent("Поръчката е архивирана.");
  });
});

describe("DeliveryDialog — Wave 4 Issue 38 (labor warranty prefill)", () => {
  function renderDialog(props: Partial<Parameters<typeof DeliveryDialog>[0]> = {}) {
    const onConfirm = vi.fn();
    render(
      <DeliveryDialog
        open
        onClose={noop}
        onConfirm={onConfirm}
        accessories={[]}
        onToggleReturned={noop}
        submitting={false}
        error={null}
        orderWarrantyDays={null}
        laborWarrantyDefault={null}
        {...props}
      />,
    );
    return { onConfirm };
  }

  it("prefills from the company labor default when the order has no explicit warranty yet", () => {
    renderDialog({ orderWarrantyDays: null, laborWarrantyDefault: 90 });
    expect(screen.getByLabelText("Гаранция (дни)")).toHaveValue(90);
  });

  it("prefers the order's own already-chosen warranty over the company default", () => {
    renderDialog({ orderWarrantyDays: 30, laborWarrantyDefault: 90 });
    expect(screen.getByLabelText("Гаранция (дни)")).toHaveValue(30);
  });

  it("respects an explicit order warranty of 0, never overwriting it with the default", () => {
    renderDialog({ orderWarrantyDays: 0, laborWarrantyDefault: 90 });
    expect(screen.getByLabelText("Гаранция (дни)")).toHaveValue(0);
  });

  it("leaves the field empty when neither the order nor the company has a value", () => {
    renderDialog({ orderWarrantyDays: null, laborWarrantyDefault: null });
    expect(screen.getByLabelText("Гаранция (дни)")).toHaveValue(null);
  });

  it("submits the (possibly user-overridden) value on confirm", async () => {
    const user = userEvent.setup();
    const { onConfirm } = renderDialog({ orderWarrantyDays: null, laborWarrantyDefault: 90 });

    const input = screen.getByLabelText("Гаранция (дни)");
    await user.clear(input);
    await user.type(input, "45");
    await user.click(screen.getByRole("button", { name: "Предай" }));

    expect(onConfirm).toHaveBeenCalledWith(45, null);
  });
});
