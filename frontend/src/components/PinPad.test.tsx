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

  // Regression test for the follow-up bug found during review of the digit
  // -loss fix: confirm's onClick read `pin` correctly, but nothing stopped
  // it running twice - two confirm clicks landing in the same batch (same
  // mechanism as the digit-loss bug: no re-render happens between them)
  // both saw the button as not-yet-disabled and both called onSubmit. A
  // useState-backed guard would have the identical stale-closure problem;
  // only a ref mutation is visible to the second call within the same batch.
  it("invokes onSubmit only once when confirm is activated twice in the same batch", () => {
    const onSubmit = vi.fn();
    render(<PinPad onSubmit={onSubmit} />);

    act(() => {
      for (const digit of ["1", "2", "3", "4"]) {
        fireEvent.click(screen.getByRole("button", { name: digit }));
      }
    });

    act(() => {
      fireEvent.click(screen.getByRole("button", { name: "Потвърди" }));
      fireEvent.click(screen.getByRole("button", { name: "Потвърди" }));
    });

    expect(onSubmit).toHaveBeenCalledTimes(1);
    expect(onSubmit).toHaveBeenCalledWith("1234");
  });

  it("disables digits, clear, and confirm while the disabled prop is set", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    const { rerender } = render(<PinPad onSubmit={onSubmit} />);

    await user.click(screen.getByRole("button", { name: "1" }));
    rerender(<PinPad onSubmit={onSubmit} disabled />);

    expect(screen.getByRole("button", { name: "2" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Изтрий" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Потвърди" })).toBeDisabled();
  });

  it("the confirm guard resets on the next entry, so a real retry after submitting still works", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    render(<PinPad onSubmit={onSubmit} />);

    for (const digit of ["1", "2", "3", "4"]) {
      await user.click(screen.getByRole("button", { name: digit }));
    }
    await user.click(screen.getByRole("button", { name: "Потвърди" }));

    for (const digit of ["5", "6", "7", "8"]) {
      await user.click(screen.getByRole("button", { name: digit }));
    }
    await user.click(screen.getByRole("button", { name: "Потвърди" }));

    expect(onSubmit).toHaveBeenCalledTimes(2);
    expect(onSubmit).toHaveBeenNthCalledWith(1, "1234");
    expect(onSubmit).toHaveBeenNthCalledWith(2, "5678");
  });
});
