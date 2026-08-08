import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { MoneyCard } from "./MoneyCard";

describe("MoneyCard", () => {
  it("displays the canonical total, paid amount and remaining balance", () => {
    render(<MoneyCard estimatedTotal={200} paidAmount={150} balance={50} />);

    expect(screen.getByText("200.00 €")).toBeInTheDocument();
    expect(screen.getByText("Платено")).toBeInTheDocument();
    expect(screen.getByText("150.00 €")).toBeInTheDocument();
    expect(screen.getByText("Остатък")).toBeInTheDocument();
    expect(screen.getByText("50.00 €")).toBeInTheDocument();
  });

  it("shows a negative balance as-is on overpayment", () => {
    render(<MoneyCard estimatedTotal={50} paidAmount={80} balance={-30} />);
    expect(screen.getByText("-30.00 €")).toBeInTheDocument();
  });

  it("does not render its own Invoice action — InvoiceCard owns Issue", () => {
    render(<MoneyCard estimatedTotal={0} paidAmount={0} balance={0} />);
    expect(screen.queryByRole("button", { name: "Издай фактура" })).not.toBeInTheDocument();
  });
});
