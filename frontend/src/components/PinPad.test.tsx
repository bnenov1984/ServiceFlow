import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { PinPad } from "./PinPad";

describe("PinPad", () => {
  it("collects digits and submits, then clears", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    render(<PinPad onSubmit={onSubmit} />);

    for (const digit of ["1", "2", "3", "4"]) {
      await user.click(screen.getByRole("button", { name: digit }));
    }
    await user.click(screen.getByRole("button", { name: "Потвърди" }));

    expect(onSubmit).toHaveBeenCalledWith("1234");
    // pad resets after submit — confirm is disabled again
    expect(screen.getByRole("button", { name: "Потвърди" })).toBeDisabled();
  });

  it("clear button wipes the entry", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    render(<PinPad onSubmit={onSubmit} />);

    await user.click(screen.getByRole("button", { name: "5" }));
    await user.click(screen.getByRole("button", { name: "Изтрий" }));
    expect(screen.getByRole("button", { name: "Потвърди" })).toBeDisabled();
    expect(onSubmit).not.toHaveBeenCalled();
  });
});
