import { describe, expect, it } from "vitest";
import { initialsOf } from "./Avatar";

describe("initialsOf", () => {
  it("handles Cyrillic names", () => {
    expect(initialsOf("Мария Иванова")).toBe("МИ");
    expect(initialsOf("Иво")).toBe("И");
  });

  it("ignores extra whitespace and extra words", () => {
    expect(initialsOf("  Иван  Петров  Георгиев ")).toBe("ИП");
  });
});
