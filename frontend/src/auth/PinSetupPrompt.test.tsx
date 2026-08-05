import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { PinSetupPrompt } from "./PinSetupPrompt";

const mockPost = vi.fn();
vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../lib/api")>("../lib/api");
  return { ...actual, api: { ...actual.api, post: (...args: unknown[]) => mockPost(...args) } };
});

const mockUseAuth = vi.fn();
vi.mock("./AuthContext", () => ({ useAuth: () => mockUseAuth() }));

describe("PinSetupPrompt", () => {
  beforeEach(() => {
    mockPost.mockReset();
    localStorage.clear();
  });

  it("shows the nudge when the user has no PIN and has not dismissed it before", () => {
    mockUseAuth.mockReturnValue({ me: { user_id: "u1", has_pin: false }, refresh: vi.fn() });
    render(<PinSetupPrompt />);

    expect(screen.getByText("Задайте PIN за бързо превключване")).toBeInTheDocument();
  });

  it("renders nothing once the user already has a PIN", () => {
    mockUseAuth.mockReturnValue({ me: { user_id: "u1", has_pin: true }, refresh: vi.fn() });
    render(<PinSetupPrompt />);

    expect(screen.queryByText("Задайте PIN за бързо превключване")).not.toBeInTheDocument();
  });

  it("dismisses on click and never shows again for this user (persisted)", async () => {
    mockUseAuth.mockReturnValue({ me: { user_id: "u1", has_pin: false }, refresh: vi.fn() });
    const { unmount } = render(<PinSetupPrompt />);
    const user = userEvent.setup();

    await user.click(screen.getByRole("button", { name: "По-късно" }));
    expect(screen.queryByText("Задайте PIN за бързо превключване")).not.toBeInTheDocument();

    unmount();
    render(<PinSetupPrompt />);
    expect(screen.queryByText("Задайте PIN за бързо превключване")).not.toBeInTheDocument();
  });

  it("opens a dialog with the set-PIN form and dismisses the nudge for good on success", async () => {
    mockUseAuth.mockReturnValue({ me: { user_id: "u1", has_pin: false }, refresh: vi.fn() });
    mockPost.mockResolvedValue({ has_pin: true });
    render(<PinSetupPrompt />);
    const user = userEvent.setup();

    await user.click(screen.getByRole("button", { name: "Задайте PIN" }));
    for (const d of "1234") await user.click(screen.getByRole("button", { name: d }));
    await user.click(screen.getByRole("button", { name: "Потвърди" }));
    for (const d of "1234") await user.click(screen.getByRole("button", { name: d }));
    await user.click(screen.getByRole("button", { name: "Потвърди" }));

    await waitFor(() =>
      expect(screen.queryByText("Задайте PIN за бързо превключване")).not.toBeInTheDocument());
    expect(localStorage.getItem("bos.pinPromptDismissed.u1")).toBe("1");
  });
});
