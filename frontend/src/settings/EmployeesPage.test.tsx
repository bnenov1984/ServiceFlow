import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "../lib/api";
import { EmployeesPage } from "./EmployeesPage";

const mockGet = vi.fn();
const mockPost = vi.fn();
const mockPatch = vi.fn();
vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../lib/api")>("../lib/api");
  return {
    ...actual,
    api: {
      ...actual.api,
      get: (...args: unknown[]) => mockGet(...args),
      post: (...args: unknown[]) => mockPost(...args),
      patch: (...args: unknown[]) => mockPatch(...args),
    },
  };
});

const mockRefresh = vi.fn();
const mockUseAuth = vi.fn();
vi.mock("../auth/AuthContext", () => ({
  useAuth: () => mockUseAuth(),
}));

const OWNER_ME = {
  user_id: "u1", name: "Мария", email: "m@a.bg", is_owner: true, language: "bg",
  company_id: "c1", csrf_token: "t", active_modules: [], seat_limit: 5, seat_usage: 2,
};

const WORKER_ME = { ...OWNER_ME, is_owner: false };

const EMPLOYEES = [
  { id: "u1", name: "Мария", email: "m@a.bg", is_owner: true, is_active: true },
  { id: "u2", name: "Иван", email: "ivan@a.bg", is_owner: false, is_active: true },
  { id: "u3", name: "Стефан", email: "stefan@a.bg", is_owner: false, is_active: false },
];

function renderPage(queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })) {
  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <EmployeesPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return queryClient;
}

async function fillAddForm(user: ReturnType<typeof userEvent.setup>, overrides: Partial<{
  name: string; email: string; password: string;
}> = {}) {
  await user.type(screen.getByLabelText("Име"), overrides.name ?? "Нов Служител");
  await user.type(screen.getByLabelText("Имейл"), overrides.email ?? "new@a.bg");
  await user.type(screen.getByLabelText("Парола"), overrides.password ?? "парола-123456");
}

// Two ConfirmDialogs (deactivate, demote) coexist in the DOM at all times
// (jsdom keeps a closed <dialog>'s content mounted) — scope to the one whose
// title text matches, rather than a bare "Потвърди"/"Отказ" query.
function dialogByTitle(title: string): HTMLElement {
  const found = [...document.querySelectorAll("dialog")].find((d) => d.textContent?.includes(title));
  if (!found) throw new Error(`dialog titled "${title}" not found in the DOM`);
  return found as HTMLElement;
}

describe("EmployeesPage", () => {
  beforeEach(() => {
    mockGet.mockReset();
    mockPost.mockReset();
    mockPatch.mockReset();
    mockRefresh.mockReset();
    mockUseAuth.mockReset();
    mockUseAuth.mockReturnValue({ me: OWNER_ME, isLoading: false, refresh: mockRefresh, logout: vi.fn() });
  });

  it("shows an access-denied state for a non-owner and makes no list request", () => {
    mockUseAuth.mockReturnValue({ me: WORKER_ME, isLoading: false, refresh: mockRefresh, logout: vi.fn() });
    renderPage();

    expect(screen.getByText("Достъпът е само за собственика на компанията.")).toBeInTheDocument();
    expect(mockGet).not.toHaveBeenCalled();
  });

  it("shows the seat-usage banner and the employee list with role/status labels", async () => {
    mockGet.mockResolvedValue(EMPLOYEES);
    renderPage();

    expect(screen.getByText("Места (използвани/лимит): 2/5")).toBeInTheDocument();
    expect(await screen.findByText("Иван")).toBeInTheDocument();
    expect(screen.getByText("Стефан")).toBeInTheDocument();
    expect(screen.getAllByText("Собственик")).toHaveLength(1);
    expect(screen.getAllByText("Служител")).toHaveLength(2);
    expect(screen.getAllByText("Активен")).toHaveLength(2);
    expect(screen.getByText("Неактивен")).toBeInTheDocument();
    expect(mockGet).toHaveBeenCalledWith("/users?include_inactive=true");
  });

  it("no longer shows a 'Моят PIN' card - self-service PIN moved to the header account menu", async () => {
    mockGet.mockResolvedValue(EMPLOYEES);
    renderPage();

    expect(await screen.findByText("Иван")).toBeInTheDocument();
    expect(screen.queryByText("Моят PIN")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Задайте PIN" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Смени PIN" })).not.toBeInTheDocument();
  });

  it("shows an empty state when there are no employees", async () => {
    mockGet.mockResolvedValue([]);
    renderPage();

    expect(await screen.findByText("Няма служители.")).toBeInTheDocument();
  });

  it("blocks submission on empty required fields, without calling the API", async () => {
    mockGet.mockResolvedValue(EMPLOYEES);
    renderPage();
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "Добави служител" }));

    expect(mockPost).not.toHaveBeenCalled();
    expect(await screen.findAllByRole("alert")).not.toHaveLength(0);
  });

  it("submits the exact expected payload and invalidates both the employees list and me", async () => {
    mockGet.mockResolvedValue(EMPLOYEES);
    mockPost.mockResolvedValue({ id: "u4", name: "Нов Служител", email: "new@a.bg", is_owner: false, is_active: true });
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    queryClient.setQueryData(["me"], OWNER_ME);
    renderPage(queryClient);
    const user = userEvent.setup();

    await screen.findByText("Иван");
    await fillAddForm(user);
    await user.click(screen.getByRole("button", { name: "Добави служител" }));

    await waitFor(() => expect(mockPost).toHaveBeenCalledWith("/users", {
      name: "Нов Служител", email: "new@a.bg", password: "парола-123456",
      is_owner: false, pin: undefined,
    }));
    await waitFor(() => expect(mockRefresh).toHaveBeenCalled());
  });

  it("shows the mapped conflict message on a 409 email_taken, clearing only the password", async () => {
    mockGet.mockResolvedValue(EMPLOYEES);
    mockPost.mockRejectedValue(new ApiError(409, "employee_error", "errors.employees.email_taken"));
    renderPage();
    const user = userEvent.setup();

    await screen.findByText("Иван");
    await fillAddForm(user);
    await user.click(screen.getByRole("button", { name: "Добави служител" }));

    expect(await screen.findByText("Имейлът вече се използва.")).toBeInTheDocument();
    expect(screen.getByLabelText("Име")).toHaveValue("Нов Служител");
    expect(screen.getByLabelText("Парола")).toHaveValue("");
  });

  it("shows a distinct message when the seat limit is reached on create", async () => {
    mockGet.mockResolvedValue(EMPLOYEES);
    mockPost.mockRejectedValue(new ApiError(409, "employee_error", "errors.employees.seat_limit_reached"));
    renderPage();
    const user = userEvent.setup();

    await screen.findByText("Иван");
    await fillAddForm(user);
    await user.click(screen.getByRole("button", { name: "Добави служител" }));

    expect(await screen.findByText("Достигнат е лимитът на местата за тази компания.")).toBeInTheDocument();
  });

  it("opens a confirm dialog before deactivating, without calling the API yet", async () => {
    mockGet.mockResolvedValue(EMPLOYEES);
    renderPage();
    const user = userEvent.setup();

    await screen.findByText("Иван");
    const deactivateButtons = screen.getAllByRole("button", { name: "Деактивирай" });
    await user.click(deactivateButtons[0]);

    expect(screen.getByText("Сигурни ли сте, че искате да деактивирате този служител?")).toBeInTheDocument();
    expect(mockPatch).not.toHaveBeenCalled();
  });

  it("makes no API call when the deactivate confirmation is cancelled", async () => {
    mockGet.mockResolvedValue(EMPLOYEES);
    renderPage();
    const user = userEvent.setup();

    await screen.findByText("Иван");
    await user.click(screen.getAllByRole("button", { name: "Деактивирай" })[0]);
    await user.click(within(dialogByTitle("Деактивиране на служител")).getByRole("button", { name: "Отказ" }));

    expect(mockPatch).not.toHaveBeenCalled();
  });

  it("deactivates on confirmation, calling PATCH with is_active: false on the right id", async () => {
    mockGet.mockResolvedValue(EMPLOYEES);
    mockPatch.mockResolvedValue({ ...EMPLOYEES[1], is_active: false });
    renderPage();
    const user = userEvent.setup();

    const ivanRow = (await screen.findByText("Иван")).closest("li");
    if (!ivanRow) throw new Error("Ivan's row not found");
    await user.click(within(ivanRow).getByRole("button", { name: "Деактивирай" }));
    await user.click(within(dialogByTitle("Деактивиране на служител")).getByRole("button", { name: "Потвърди" }));

    await waitFor(() => expect(mockPatch).toHaveBeenCalledWith("/users/u2", { is_active: false }));
  });

  it("reactivates directly, unconfirmed, calling PATCH with is_active: true", async () => {
    mockGet.mockResolvedValue(EMPLOYEES);
    mockPatch.mockResolvedValue({ ...EMPLOYEES[2], is_active: true });
    renderPage();
    const user = userEvent.setup();

    await screen.findByText("Стефан");
    await user.click(screen.getByRole("button", { name: "Активирай" }));

    await waitFor(() => expect(mockPatch).toHaveBeenCalledWith("/users/u3", { is_active: true }));
  });

  it("shows a distinct message when deactivating the last active owner", async () => {
    mockGet.mockResolvedValue(EMPLOYEES);
    mockPatch.mockRejectedValue(new ApiError(409, "employee_error", "errors.employees.last_owner_protected"));
    renderPage();
    const user = userEvent.setup();

    await screen.findByText("Иван");
    const deactivateButtons = screen.getAllByRole("button", { name: "Деактивирай" });
    await user.click(deactivateButtons[0]);
    await user.click(within(dialogByTitle("Деактивиране на служител")).getByRole("button", { name: "Потвърди" }));

    expect(await screen.findByText("Компанията трябва да има поне един активен собственик.")).toBeInTheDocument();
  });

  it("prevents a duplicate create request from a rapid double-click", async () => {
    mockGet.mockResolvedValue(EMPLOYEES);
    let resolvePost: (v: unknown) => void = () => {};
    mockPost.mockReturnValue(new Promise((resolve) => { resolvePost = resolve; }));
    renderPage();
    const user = userEvent.setup();

    await screen.findByText("Иван");
    await fillAddForm(user);
    const submitButton = screen.getByRole("button", { name: "Добави служител" });
    await user.click(submitButton);
    await user.click(submitButton);

    resolvePost({ id: "u4", name: "Нов Служител", email: "new@a.bg", is_owner: false, is_active: true });
    await waitFor(() => expect(mockPost).toHaveBeenCalledTimes(1));
  });

  it("prevents a duplicate reactivate request from a rapid double-click", async () => {
    mockGet.mockResolvedValue(EMPLOYEES);
    let resolvePatch: (v: unknown) => void = () => {};
    mockPatch.mockReturnValue(new Promise((resolve) => { resolvePatch = resolve; }));
    renderPage();
    const user = userEvent.setup();

    await screen.findByText("Стефан");
    const reactivateButton = screen.getByRole("button", { name: "Активирай" });
    await user.click(reactivateButton);
    await user.click(reactivateButton);

    resolvePatch({ ...EMPLOYEES[2], is_active: true });
    await waitFor(() => expect(mockPatch).toHaveBeenCalledTimes(1));
  });

  it("promotes a worker to owner directly, unconfirmed, calling PATCH with is_owner: true", async () => {
    mockGet.mockResolvedValue(EMPLOYEES);
    mockPatch.mockResolvedValue({ ...EMPLOYEES[1], is_owner: true });
    renderPage();
    const user = userEvent.setup();

    const ivanRow = (await screen.findByText("Иван")).closest("li");
    if (!ivanRow) throw new Error("Ivan's row not found");
    await user.click(within(ivanRow).getByRole("button", { name: "Направи собственик" }));

    await waitFor(() => expect(mockPatch).toHaveBeenCalledWith("/users/u2", { is_owner: true }));
  });

  it("opens a confirm dialog before demoting an owner, without calling the API yet", async () => {
    mockGet.mockResolvedValue(EMPLOYEES);
    renderPage();
    const user = userEvent.setup();

    const mariaRow = (await screen.findByText("Мария")).closest("li");
    if (!mariaRow) throw new Error("Maria's row not found");
    await user.click(within(mariaRow).getByRole("button", { name: "Направи служител" }));

    expect(screen.getByText("Сигурни ли сте, че искате този служител да спре да бъде собственик?"))
      .toBeInTheDocument();
    expect(mockPatch).not.toHaveBeenCalled();
  });

  it("makes no API call when the demote confirmation is cancelled", async () => {
    mockGet.mockResolvedValue(EMPLOYEES);
    renderPage();
    const user = userEvent.setup();

    const mariaRow = (await screen.findByText("Мария")).closest("li");
    if (!mariaRow) throw new Error("Maria's row not found");
    await user.click(within(mariaRow).getByRole("button", { name: "Направи служител" }));
    await user.click(within(dialogByTitle("Промяна на роля")).getByRole("button", { name: "Отказ" }));

    expect(mockPatch).not.toHaveBeenCalled();
  });

  it("demotes on confirmation, calling PATCH with is_owner: false on the right id", async () => {
    mockGet.mockResolvedValue(EMPLOYEES);
    mockPatch.mockResolvedValue({ ...EMPLOYEES[0], is_owner: false });
    renderPage();
    const user = userEvent.setup();

    const mariaRow = (await screen.findByText("Мария")).closest("li");
    if (!mariaRow) throw new Error("Maria's row not found");
    await user.click(within(mariaRow).getByRole("button", { name: "Направи служител" }));
    await user.click(within(dialogByTitle("Промяна на роля")).getByRole("button", { name: "Потвърди" }));

    await waitFor(() => expect(mockPatch).toHaveBeenCalledWith("/users/u1", { is_owner: false }));
  });

  it("shows a distinct message when demoting the last active owner", async () => {
    mockGet.mockResolvedValue(EMPLOYEES);
    mockPatch.mockRejectedValue(new ApiError(409, "employee_error", "errors.employees.last_owner_protected"));
    renderPage();
    const user = userEvent.setup();

    const mariaRow = (await screen.findByText("Мария")).closest("li");
    if (!mariaRow) throw new Error("Maria's row not found");
    await user.click(within(mariaRow).getByRole("button", { name: "Направи служител" }));
    await user.click(within(dialogByTitle("Промяна на роля")).getByRole("button", { name: "Потвърди" }));

    expect(await screen.findByText("Компанията трябва да има поне един активен собственик.")).toBeInTheDocument();
  });

  // Regression tests for the confirmed bug: the error was set in state and
  // rendered, but as a sibling in the page body - a native <dialog> shown
  // via showModal() sits in the browser's top layer, above the rest of the
  // page, so that error was invisible while the dialog stayed open. jsdom
  // doesn't enforce that visual stacking (it'll happily report page-body
  // text as "in the document" either way), so these assert DOM *nesting* -
  // the error must be `within` the dialog itself, not just present anywhere.
  it("keeps the deactivate dialog open and shows the error inside it on failure", async () => {
    mockGet.mockResolvedValue(EMPLOYEES);
    mockPatch.mockRejectedValue(new ApiError(500, "unknown", "errors.internal"));
    renderPage();
    const user = userEvent.setup();

    const ivanRow = (await screen.findByText("Иван")).closest("li");
    if (!ivanRow) throw new Error("Ivan's row not found");
    await user.click(within(ivanRow).getByRole("button", { name: "Деактивирай" }));
    const dialog = dialogByTitle("Деактивиране на служител");
    await user.click(within(dialog).getByRole("button", { name: "Потвърди" }));

    expect(await within(dialog).findByText("Възникна неочаквана грешка. Опитайте отново."))
      .toBeInTheDocument();
    expect(dialog).toHaveAttribute("open");
    expect(mockPatch).toHaveBeenCalledTimes(1);
  });

  it("allows retrying a failed deactivate without closing the dialog first", async () => {
    mockGet.mockResolvedValue(EMPLOYEES);
    mockPatch
      .mockRejectedValueOnce(new ApiError(500, "unknown", "errors.internal"))
      .mockResolvedValueOnce({ ...EMPLOYEES[1], is_active: false });
    renderPage();
    const user = userEvent.setup();

    const ivanRow = (await screen.findByText("Иван")).closest("li");
    if (!ivanRow) throw new Error("Ivan's row not found");
    await user.click(within(ivanRow).getByRole("button", { name: "Деактивирай" }));
    const dialog = dialogByTitle("Деактивиране на служител");
    await user.click(within(dialog).getByRole("button", { name: "Потвърди" }));
    await within(dialog).findByText("Възникна неочаквана грешка. Опитайте отново.");

    await user.click(within(dialog).getByRole("button", { name: "Потвърди" }));

    await waitFor(() => expect(mockPatch).toHaveBeenCalledTimes(2));
    expect(mockPatch).toHaveBeenNthCalledWith(2, "/users/u2", { is_active: false });
  });

  it("cancelling after a failed deactivate does not leak the error into the next dialog opened", async () => {
    mockGet.mockResolvedValue(EMPLOYEES);
    mockPatch.mockRejectedValue(new ApiError(500, "unknown", "errors.internal"));
    renderPage();
    const user = userEvent.setup();

    const ivanRow = (await screen.findByText("Иван")).closest("li");
    if (!ivanRow) throw new Error("Ivan's row not found");
    await user.click(within(ivanRow).getByRole("button", { name: "Деактивирай" }));
    const deactivateDialog = dialogByTitle("Деактивиране на служител");
    await user.click(within(deactivateDialog).getByRole("button", { name: "Потвърди" }));
    await within(deactivateDialog).findByText("Възникна неочаквана грешка. Опитайте отново.");
    await user.click(within(deactivateDialog).getByRole("button", { name: "Отказ" }));

    const mariaRow = (await screen.findByText("Мария")).closest("li");
    if (!mariaRow) throw new Error("Maria's row not found");
    await user.click(within(mariaRow).getByRole("button", { name: "Направи служител" }));
    const demoteDialog = dialogByTitle("Промяна на роля");

    expect(within(demoteDialog).queryByText("Възникна неочаквана грешка. Опитайте отново."))
      .not.toBeInTheDocument();
  });

  it("keeps the demote dialog open and shows the error inside it on failure", async () => {
    mockGet.mockResolvedValue(EMPLOYEES);
    mockPatch.mockRejectedValue(new ApiError(500, "unknown", "errors.internal"));
    renderPage();
    const user = userEvent.setup();

    const mariaRow = (await screen.findByText("Мария")).closest("li");
    if (!mariaRow) throw new Error("Maria's row not found");
    await user.click(within(mariaRow).getByRole("button", { name: "Направи служител" }));
    const dialog = dialogByTitle("Промяна на роля");
    await user.click(within(dialog).getByRole("button", { name: "Потвърди" }));

    expect(await within(dialog).findByText("Възникна неочаквана грешка. Опитайте отново."))
      .toBeInTheDocument();
    expect(dialog).toHaveAttribute("open");
  });

  it("still shows a page-level error for reactivate (no confirm dialog) on failure", async () => {
    mockGet.mockResolvedValue(EMPLOYEES);
    mockPatch.mockRejectedValue(new ApiError(500, "unknown", "errors.internal"));
    renderPage();
    const user = userEvent.setup();

    await screen.findByText("Стефан");
    await user.click(screen.getByRole("button", { name: "Активирай" }));

    expect(await screen.findByText("Възникна неочаквана грешка. Опитайте отново.")).toBeInTheDocument();
  });

  it("prevents a duplicate promote request from a rapid double-click", async () => {
    mockGet.mockResolvedValue(EMPLOYEES);
    let resolvePatch: (v: unknown) => void = () => {};
    mockPatch.mockReturnValue(new Promise((resolve) => { resolvePatch = resolve; }));
    renderPage();
    const user = userEvent.setup();

    const ivanRow = (await screen.findByText("Иван")).closest("li");
    if (!ivanRow) throw new Error("Ivan's row not found");
    const promoteButton = within(ivanRow).getByRole("button", { name: "Направи собственик" });
    await user.click(promoteButton);
    await user.click(promoteButton);

    resolvePatch({ ...EMPLOYEES[1], is_owner: true });
    await waitFor(() => expect(mockPatch).toHaveBeenCalledTimes(1));
  });
});
