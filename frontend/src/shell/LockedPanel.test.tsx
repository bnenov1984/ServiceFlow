import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { LockedPanel } from "./AppShell";

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

const mockLogout = vi.fn();
const mockRefresh = vi.fn();
vi.mock("../auth/AuthContext", () => ({
  useAuth: () => ({ me: { user_id: "u1", name: "Мария" }, logout: mockLogout, refresh: mockRefresh }),
}));

function renderPanel(onUnlocked = vi.fn()) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <LockedPanel onUnlocked={onUnlocked} />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return onUnlocked;
}

async function clickUser(user: ReturnType<typeof userEvent.setup>, name: string) {
  await user.click(await screen.findByRole("button", { name: new RegExp(name) }));
}

describe("LockedPanel — no-PIN users cannot enter the normal PIN-switch flow", () => {
  beforeEach(() => {
    mockGet.mockReset();
    mockPost.mockReset();
    mockLogout.mockReset();
    mockRefresh.mockReset();
  });

  it("shows 'Задайте PIN' / 'Влезте с парола' for the current user when they have no PIN, never the PIN pad", async () => {
    mockGet.mockResolvedValue([
      { id: "u1", name: "Мария", is_owner: true, is_active: true, has_pin: false },
    ]);
    renderPanel();
    const user = userEvent.setup();

    await clickUser(user, "Мария");

    expect(screen.getByText("Нямате зададен PIN")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Задайте PIN" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Влезте с парола" })).toBeInTheDocument();
    expect(screen.queryByLabelText("PIN")).not.toBeInTheDocument();
    expect(mockPost).not.toHaveBeenCalled();
  });

  it("disables another user's entry entirely when they have no PIN", async () => {
    mockGet.mockResolvedValue([
      { id: "u1", name: "Мария", is_owner: true, is_active: true, has_pin: true },
      { id: "u2", name: "Иво", is_owner: false, is_active: true, has_pin: false },
    ]);
    renderPanel();
    const user = userEvent.setup();

    const ivoButton = await screen.findByRole("button", { name: /Иво/ });
    expect(ivoButton).toBeDisabled();
    await user.click(ivoButton);
    expect(screen.queryByLabelText("PIN")).not.toBeInTheDocument();
  });

  it("never shows 'Грешен PIN' for a user with no PIN, because pin-switch is never called for them", async () => {
    mockGet.mockResolvedValue([
      { id: "u1", name: "Мария", is_owner: true, is_active: true, has_pin: false },
    ]);
    renderPanel();
    const user = userEvent.setup();

    await clickUser(user, "Мария");

    expect(screen.queryByText("Грешен PIN.")).not.toBeInTheDocument();
    expect(mockPost).not.toHaveBeenCalledWith("/auth/pin-switch", expect.anything());
  });
});

describe("LockedPanel — setting a PIN from the lock screen", () => {
  beforeEach(() => {
    mockGet.mockReset();
    mockPost.mockReset();
    mockRefresh.mockReset();
  });

  it("unlocks immediately after successfully setting a PIN", async () => {
    mockGet.mockResolvedValue([
      { id: "u1", name: "Мария", is_owner: true, is_active: true, has_pin: false },
    ]);
    mockPost.mockResolvedValue({ has_pin: true });
    const onUnlocked = renderPanel();
    const user = userEvent.setup();

    await clickUser(user, "Мария");
    await user.click(screen.getByRole("button", { name: "Задайте PIN" }));

    for (const d of "1234") await user.click(screen.getByRole("button", { name: d }));
    await user.click(screen.getByRole("button", { name: "Потвърди" }));
    for (const d of "1234") await user.click(screen.getByRole("button", { name: d }));
    await user.click(screen.getByRole("button", { name: "Потвърди" }));

    await waitFor(() => expect(mockPost).toHaveBeenCalledWith("/auth/pin", { pin: "1234" }));
    await waitFor(() => expect(onUnlocked).toHaveBeenCalled());
  });
});

describe("LockedPanel — idle-lock still allows logout/password recovery", () => {
  beforeEach(() => {
    mockGet.mockReset();
    mockLogout.mockReset();
    mockLogout.mockResolvedValue(undefined);
  });

  it("keeps a Logout button available on the initial user list", async () => {
    mockGet.mockResolvedValue([
      { id: "u1", name: "Мария", is_owner: true, is_active: true, has_pin: false },
    ]);
    renderPanel();

    expect(await screen.findByRole("button", { name: "Изход" })).toBeInTheDocument();
  });

  it("'Влезте с парола' for a no-PIN self logs out", async () => {
    mockGet.mockResolvedValue([
      { id: "u1", name: "Мария", is_owner: true, is_active: true, has_pin: false },
    ]);
    renderPanel();
    const user = userEvent.setup();

    await clickUser(user, "Мария");
    await user.click(screen.getByRole("button", { name: "Влезте с парола" }));

    await waitFor(() => expect(mockLogout).toHaveBeenCalled());
  });

  it("keeps Logout available even mid-PIN-entry for a user who does have a PIN", async () => {
    mockGet.mockResolvedValue([
      { id: "u1", name: "Мария", is_owner: true, is_active: true, has_pin: true },
    ]);
    renderPanel();
    const user = userEvent.setup();

    await clickUser(user, "Мария");
    expect(screen.getByRole("button", { name: "Изход" })).toBeInTheDocument();
  });
});

describe("LockedPanel — existing PIN-switch behavior for a user with a PIN is unchanged", () => {
  beforeEach(() => {
    mockGet.mockReset();
    mockPost.mockReset();
  });

  it("submits the entered PIN via pin-switch and unlocks on success", async () => {
    mockGet.mockResolvedValue([
      { id: "u1", name: "Мария", is_owner: true, is_active: true, has_pin: true },
    ]);
    mockPost.mockResolvedValue({ name: "Мария" });
    const onUnlocked = renderPanel();
    const user = userEvent.setup();

    await clickUser(user, "Мария");
    for (const d of "1234") await user.click(screen.getByRole("button", { name: d }));
    await user.click(screen.getByRole("button", { name: "Потвърди" }));

    await waitFor(() => expect(mockPost).toHaveBeenCalledWith(
      "/auth/pin-switch", { user_id: "u1", pin: "1234" },
    ));
    await waitFor(() => expect(onUnlocked).toHaveBeenCalled());
  });

  it("shows a wrong-PIN error and stays locked on failure", async () => {
    mockGet.mockResolvedValue([
      { id: "u1", name: "Мария", is_owner: true, is_active: true, has_pin: true },
    ]);
    const { ApiError } = await import("../lib/api");
    mockPost.mockRejectedValue(new ApiError(401, "pin_failed", "errors.auth.invalid_pin"));
    const onUnlocked = renderPanel();
    const user = userEvent.setup();

    await clickUser(user, "Мария");
    for (const d of "0000") await user.click(screen.getByRole("button", { name: d }));
    await user.click(screen.getByRole("button", { name: "Потвърди" }));

    expect(await screen.findByText("Грешен PIN.")).toBeInTheDocument();
    expect(onUnlocked).not.toHaveBeenCalled();
  });
});
