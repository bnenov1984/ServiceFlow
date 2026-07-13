import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it } from "vitest";
import { AccessoriesChecklist } from "./AccessoriesChecklist";

/** Wires the checklist the same way OrderStep does (functional setState via
 * onToggle) so a regression to array-snapshot onChange would show up here. */
function Harness() {
  const [selected, setSelected] = useState<string[]>([]);
  return (
    <AccessoriesChecklist
      selected={selected}
      onToggle={(name) =>
        setSelected((prev) =>
          prev.includes(name) ? prev.filter((a) => a !== name) : [...prev, name],
        )
      }
    />
  );
}

describe("AccessoriesChecklist", () => {
  it("keeps both picks when two chips are toggled back-to-back", async () => {
    const user = userEvent.setup();
    render(<Harness />);

    await user.click(screen.getByRole("button", { name: "Зарядно" }));
    await user.click(screen.getByRole("button", { name: "Кутия" }));

    expect(screen.getByRole("button", { name: "Зарядно" })).toHaveAttribute(
      "aria-pressed", "true",
    );
    expect(screen.getByRole("button", { name: "Кутия" })).toHaveAttribute(
      "aria-pressed", "true",
    );
  });

  it("toggling the same chip twice removes it again", async () => {
    const user = userEvent.setup();
    render(<Harness />);

    const chip = screen.getByRole("button", { name: "СИМ" });
    await user.click(chip);
    expect(chip).toHaveAttribute("aria-pressed", "true");
    await user.click(chip);
    expect(chip).toHaveAttribute("aria-pressed", "false");
  });

  it("adds a custom accessory via the free-text field", async () => {
    const user = userEvent.setup();
    render(<Harness />);

    await user.type(screen.getByPlaceholderText("Друг аксесоар…"), "Стилус");
    await user.click(screen.getByRole("button", { name: "Добави" }));

    expect(screen.getByRole("button", { name: "Стилус" })).toHaveAttribute(
      "aria-pressed", "true",
    );
  });
});
