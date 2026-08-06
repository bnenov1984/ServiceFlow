import { act, fireEvent, render, screen } from "@testing-library/react";
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

  // Regression test for the reported bug: press() read `pin` from its own
  // render's closure (`setPin(pin + digit)`), so presses dispatched close
  // enough together to land in the same React batch each computed the next
  // value off the same stale `pin`, and only the last write survived - a
  // 4-digit PIN typed quickly could silently become 1 digit. userEvent.click
  // awaits a render between clicks and never reproduced this; wrapping raw
  // fireEvent.click calls in one act() forces them into a single batch,
  // matching what actually happens under fast real touch-typing.
  it("does not drop digits when several presses land in the same batch (rapid entry)", () => {
    const onSubmit = vi.fn();
    render(<PinPad onSubmit={onSubmit} />);

    act(() => {
      for (const digit of ["1", "2", "3", "4"]) {
        fireEvent.click(screen.getByRole("button", { name: digit }));
      }
    });

    fireEvent.click(screen.getByRole("button", { name: "Потвърди" }));
    expect(onSubmit).toHaveBeenCalledWith("1234");
  });

  it("still caps entry at 8 digits when the extra presses are batched together", () => {
    const onSubmit = vi.fn();
    render(<PinPad onSubmit={onSubmit} />);

    act(() => {
      for (const digit of ["1", "2", "3", "4", "5", "6", "7", "8", "9"]) {
        fireEvent.click(screen.getByRole("button", { name: digit }));
      }
    });

    fireEvent.click(screen.getByRole("button", { name: "Потвърди" }));
    expect(onSubmit).toHaveBeenCalledWith("12345678");
  });
});
