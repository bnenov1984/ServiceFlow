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
      />,
    );

    expect(screen.getByRole("alert")).toHaveTextContent("Поръчката е архивирана.");
  });
});
