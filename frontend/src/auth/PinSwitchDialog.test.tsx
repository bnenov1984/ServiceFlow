import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { MemoryRouter } from "react-router-dom";
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

const mockLogout = vi.fn().mockResolvedValue(undefined);
vi.mock("./AuthContext", () => ({
  useAuth: () => ({ me: { user_id: "u1", name: "Мария" }, logout: mockLogout }),
}));

function renderDialog() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <MemoryRouter>
      <QueryClientProvider client={queryClient}>
        <PinSwitchDialog open onClose={() => {}} />
      </QueryClientProvider>
    </MemoryRouter>,
  );
}

// Owns `open` the same way AppShell does (`onClose={() => setPinSwitchOpen(false)}`),
// with an explicit REOPEN trigger so close/reopen regression tests read as
// what they are: close the dialog, then actually reopen the same
// always-mounted instance and check what it shows.
function Harness() {
  const [open, setOpen] = useState(true);
  return (
    <>
      {!open && (
        <button type="button" onClick={() => setOpen(true)}>
          REOPEN
        </button>
      )}
      <PinSwitchDialog open={open} onClose={() => setOpen(false)} />
    </>
  );
}

function renderHarness() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <MemoryRouter>
      <QueryClientProvider client={queryClient}>
        <Harness />
      </QueryClientProvider>
    </MemoryRouter>,
  );
}

describe("PinSwitchDialog", () => {
  beforeEach(() => {
    mockGet.mockReset();
    mockPost.mockReset();
    mockLogout.mockReset().mockResolvedValue(undefined);
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

// Regression tests for the close-lifecycle fix: Dialog never unmounts
// PinSwitchDialog's children just because `open` goes false, so before this
// fix, closing via X or Escape (unlike a successful submit) left `selected`
// - and the still-mounted PinPad's partial entry - exactly as they were,
// stale for whoever reopened the same dialog instance next.
describe("PinSwitchDialog — resets on every close path, not just success", () => {
  beforeEach(() => {
    mockGet.mockReset();
    mockPost.mockReset();
    mockLogout.mockReset().mockResolvedValue(undefined);
  });

  it("enter partial PIN, close with X, reopen -> PIN empty", async () => {
    mockGet.mockResolvedValue([
      { id: "u2", name: "Иво", is_owner: false, is_active: true, has_pin: true },
    ]);
    renderHarness();
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "Иво" }));
    await user.click(screen.getByRole("button", { name: "1" }));
    await user.click(screen.getByRole("button", { name: "2" }));
    expect(screen.getByLabelText("PIN")).toHaveTextContent("●●");

    await user.click(screen.getByRole("button", { name: "Затвори" }));
    await user.click(screen.getByRole("button", { name: "REOPEN" }));

    // back on the picker - no selected user, so no PinPad/partial entry at all
    expect(await screen.findByRole("button", { name: "Иво" })).toBeInTheDocument();
    expect(screen.queryByLabelText("PIN")).not.toBeInTheDocument();
  });

  it("select employee, close with Escape, reopen -> no selection", async () => {
    mockGet.mockResolvedValue([
      { id: "u2", name: "Иво", is_owner: false, is_active: true, has_pin: true },
    ]);
    const { container } = renderHarness();
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "Иво" }));
    expect(screen.getByLabelText("PIN")).toBeInTheDocument();

    // Dialog.tsx wires the native <dialog>'s `cancel` event (fired by the
    // browser on Escape) to the same onClose as the X button.
    const dialogEl = container.querySelector("dialog");
    if (!dialogEl) throw new Error("dialog element not found");
    fireEvent(dialogEl, new Event("cancel", { bubbles: true, cancelable: true }));

    await user.click(screen.getByRole("button", { name: "REOPEN" }));

    expect(await screen.findByRole("button", { name: "Иво" })).toBeInTheDocument();
    expect(screen.queryByLabelText("PIN")).not.toBeInTheDocument();
  });

  it("successful submit still closes and resets, so reopening shows the picker", async () => {
    mockGet.mockResolvedValue([
      { id: "u2", name: "Иво", is_owner: false, is_active: true, has_pin: true },
    ]);
    mockPost.mockResolvedValue({ name: "Иво" });
    renderHarness();
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "Иво" }));
    for (const d of "1234") {
      await user.click(screen.getByRole("button", { name: d }));
    }
    await user.click(screen.getByRole("button", { name: "Потвърди" }));

    await waitFor(() => expect(mockPost).toHaveBeenCalledWith(
      "/auth/pin-switch", { user_id: "u2", pin: "1234" },
    ));

    await user.click(await screen.findByRole("button", { name: "REOPEN" }));
    expect(await screen.findByRole("button", { name: "Иво" })).toBeInTheDocument();
  });

  // Explicitly defined behavior for closing mid-request (docs/business-os
  // PIN follow-up design): the in-flight request is not cancelled and
  // resolves in the background against the still-mounted dialog. A late
  // success still clears the query cache and calls the (already-idempotent)
  // close/reset - closing early must not crash or hang the app.
  it("closing while a submission is pending resets immediately and tolerates the request resolving later", async () => {
    mockGet.mockResolvedValue([
      { id: "u2", name: "Иво", is_owner: false, is_active: true, has_pin: true },
    ]);
    let resolvePost: (value: { name: string }) => void = () => {};
    mockPost.mockImplementation(
      () => new Promise((resolve) => { resolvePost = resolve; }),
    );
    renderHarness();
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "Иво" }));
    for (const d of "1234") {
      await user.click(screen.getByRole("button", { name: d }));
    }
    await user.click(screen.getByRole("button", { name: "Потвърди" }));

    // Close is not gated on the pending request - X still works immediately.
    await user.click(screen.getByRole("button", { name: "Затвори" }));
    expect(await screen.findByRole("button", { name: "REOPEN" })).toBeInTheDocument();

    // The delayed request resolving afterward must not throw/crash the tree.
    await act(async () => {
      resolvePost({ name: "Иво" });
    });
    expect(screen.getByRole("button", { name: "REOPEN" })).toBeInTheDocument();
  });
});
