import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MyPinCard } from "./MyPinCard";

const mockPost = vi.fn();
vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../lib/api")>("../lib/api");
  return { ...actual, api: { ...actual.api, post: (...args: unknown[]) => mockPost(...args) } };
});

const mockUseAuth = vi.fn();
vi.mock("../auth/AuthContext", () => ({ useAuth: () => mockUseAuth() }));

describe("MyPinCard", () => {
  beforeEach(() => {
    mockPost.mockReset();
  });

  it("shows the not-set hint and a 'Задайте PIN' action when the owner has no PIN", () => {
    mockUseAuth.mockReturnValue({ me: { user_id: "u1", has_pin: false }, refresh: vi.fn() });
    render(<MyPinCard />);

    expect(screen.getByText("Нямате зададен PIN за бързо превключване на потребител.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Задайте PIN" })).toBeInTheDocument();
  });

  it("shows the set hint and a 'Смени PIN' action when a PIN already exists", () => {
    mockUseAuth.mockReturnValue({ me: { user_id: "u1", has_pin: true }, refresh: vi.fn() });
    render(<MyPinCard />);

    expect(screen.getByText("Задали сте PIN за бързо превключване на потребител.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Смени PIN" })).toBeInTheDocument();
  });

  it("opens the set-PIN form, submits, and returns to the summary view", async () => {
    mockUseAuth.mockReturnValue({ me: { user_id: "u1", has_pin: false }, refresh: vi.fn() });
    mockPost.mockResolvedValue({ has_pin: true });
    render(<MyPinCard />);
    const user = userEvent.setup();

    await user.click(screen.getByRole("button", { name: "Задайте PIN" }));
    expect(screen.getByText("Нов PIN")).toBeInTheDocument();

    for (const d of "1234") await user.click(screen.getByRole("button", { name: d }));
    await user.click(screen.getByRole("button", { name: "Потвърди" }));
    for (const d of "1234") await user.click(screen.getByRole("button", { name: d }));
    await user.click(screen.getByRole("button", { name: "Потвърди" }));

    expect(await screen.findByRole("button", { name: "Задайте PIN" })).toBeInTheDocument();
    expect(mockPost).toHaveBeenCalledWith("/auth/pin", { pin: "1234" });
  });

  it("returns to the summary view on cancel without submitting", async () => {
    mockUseAuth.mockReturnValue({ me: { user_id: "u1", has_pin: true }, refresh: vi.fn() });
    render(<MyPinCard />);
    const user = userEvent.setup();

    await user.click(screen.getByRole("button", { name: "Смени PIN" }));
    await user.click(screen.getByRole("button", { name: "Отказ" }));

    expect(screen.getByRole("button", { name: "Смени PIN" })).toBeInTheDocument();
    expect(mockPost).not.toHaveBeenCalled();
  });
});
