import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { PinSwitchDialog } from "./PinSwitchDialog";

const mockGet = vi.fn();
const mockPost = vi.fn();
vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../lib/api")>("../lib/api");
  return {
    ...actual,
    api: {
      ...actual.api,
      get: (...args: unknown[]) => mockGet(...args),
      post: (...args: unknown[]) => mockPost(...args),
    },
  };
});

vi.mock("./AuthContext", () => ({
  useAuth: () => ({ me: { user_id: "u1", name: "Мария" } }),
}));

function renderDialog() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
      <PinSwitchDialog open onClose={() => {}} />
    </QueryClientProvider>,
  );
}

describe("PinSwitchDialog", () => {
  beforeEach(() => {
    mockGet.mockReset();
    mockPost.mockReset();
  });

  it("disables a user with no PIN and shows a hint, instead of opening the PIN pad", async () => {
    mockGet.mockResolvedValue([
      { id: "u2", name: "Иво", is_owner: false, is_active: true, has_pin: false },
    ]);
    renderDialog();
    const user = userEvent.setup();

    const button = await screen.findByRole("button", { name: /Иво/ });
    expect(button).toBeDisabled();
    expect(screen.getByText("Няма зададен PIN")).toBeInTheDocument();

    await user.click(button);
    expect(screen.queryByLabelText("PIN")).not.toBeInTheDocument();
  });

  it("lets a user with a PIN proceed to the normal PIN pad", async () => {
    mockGet.mockResolvedValue([
      { id: "u2", name: "Иво", is_owner: false, is_active: true, has_pin: true },
    ]);
    renderDialog();
    const user = userEvent.setup();

    const button = await screen.findByRole("button", { name: "Иво" });
    expect(button).not.toBeDisabled();
    await user.click(button);

    expect(await screen.findByLabelText("PIN")).toBeInTheDocument();
  });

  // Regression test for the PinPad confirm re-entrancy guard: two confirm
  // clicks landing in the same React batch used to both fire submitPin,
  // doubling the POST /auth/pin-switch call.
  it("does not send a duplicate POST /auth/pin-switch when confirm is activated twice in the same batch", async () => {
    mockGet.mockResolvedValue([
      { id: "u2", name: "Иво", is_owner: false, is_active: true, has_pin: true },
    ]);
    mockPost.mockResolvedValue({ name: "Иво" });
    renderDialog();
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "Иво" }));
    for (const d of "1234") {
      await user.click(screen.getByRole("button", { name: d }));
    }

    act(() => {
      fireEvent.click(screen.getByRole("button", { name: "Потвърди" }));
      fireEvent.click(screen.getByRole("button", { name: "Потвърди" }));
    });

    await waitFor(() => expect(mockPost).toHaveBeenCalledTimes(1));
    expect(mockPost).toHaveBeenCalledWith("/auth/pin-switch", { user_id: "u2", pin: "1234" });
  });
});
