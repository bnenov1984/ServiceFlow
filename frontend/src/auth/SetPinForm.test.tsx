import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "../lib/api";
import { SetPinForm } from "./SetPinForm";

const mockPost = vi.fn();
vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../lib/api")>("../lib/api");
  return { ...actual, api: { ...actual.api, post: (...args: unknown[]) => mockPost(...args) } };
});

const mockRefresh = vi.fn();
vi.mock("./AuthContext", () => ({ useAuth: () => ({ refresh: mockRefresh }) }));

async function enterPin(user: ReturnType<typeof userEvent.setup>, digits: string) {
  for (const d of digits) {
    await user.click(screen.getByRole("button", { name: d }));
  }
  await user.click(screen.getByRole("button", { name: "Потвърди" }));
}

describe("SetPinForm", () => {
  beforeEach(() => {
    mockPost.mockReset();
    mockRefresh.mockReset();
  });

  it("blocks a too-short first PIN without advancing to the confirm step", async () => {
    render(<SetPinForm onDone={() => {}} />);
    const user = userEvent.setup();

    await enterPin(user, "12");

    expect(await screen.findByText("PIN трябва да е поне 4 цифри.")).toBeInTheDocument();
    expect(screen.getByText("Нов PIN")).toBeInTheDocument();
    expect(mockPost).not.toHaveBeenCalled();
  });

  it("restarts at step one with a mismatch error when confirmation doesn't match", async () => {
    render(<SetPinForm onDone={() => {}} />);
    const user = userEvent.setup();

    await enterPin(user, "1234");
    expect(await screen.findByText("Потвърдете PIN")).toBeInTheDocument();
    await enterPin(user, "9999");

    expect(await screen.findByText("PIN кодовете не съвпадат.")).toBeInTheDocument();
    expect(screen.getByText("Нов PIN")).toBeInTheDocument();
    expect(mockPost).not.toHaveBeenCalled();
  });

  it("submits the matched PIN, refreshes auth, and calls onDone", async () => {
    mockPost.mockResolvedValue({ has_pin: true });
    const onDone = vi.fn();
    render(<SetPinForm onDone={onDone} />);
    const user = userEvent.setup();

    await enterPin(user, "1234");
    await enterPin(user, "1234");

    expect(mockPost).toHaveBeenCalledWith("/auth/pin", { pin: "1234" });
    expect(mockRefresh).toHaveBeenCalled();
    expect(onDone).toHaveBeenCalled();
  });

  it("shows a recoverable inline error on failure and restarts at step one", async () => {
    mockPost.mockRejectedValue(new ApiError(500, "unknown", "errors.internal"));
    render(<SetPinForm onDone={() => {}} />);
    const user = userEvent.setup();

    await enterPin(user, "1234");
    await enterPin(user, "1234");

    expect(await screen.findByText("Възникна неочаквана грешка. Опитайте отново.")).toBeInTheDocument();
    expect(screen.getByText("Нов PIN")).toBeInTheDocument();
  });

  it("calls onCancel when provided and clicked", async () => {
    const onCancel = vi.fn();
    render(<SetPinForm onDone={() => {}} onCancel={onCancel} />);
    const user = userEvent.setup();

    await user.click(screen.getByRole("button", { name: "Отказ" }));
    expect(onCancel).toHaveBeenCalled();
  });
});
