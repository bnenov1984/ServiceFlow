import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { PAGE_SIZE } from "./Pagination";
import { PsPage } from "./PsPage";
import type { PsAssignment, PsClient, PsDeadlineChange, PsNextAction, PsStage } from "./types";

const mockGet = vi.fn();
const mockPost = vi.fn();
vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../lib/api")>("../lib/api");
  return { ...actual, api: { ...actual.api, get: (...args: unknown[]) => mockGet(...args), post: (...args: unknown[]) => mockPost(...args) } };
});

const mockUseAuth = vi.fn();
vi.mock("../auth/AuthContext", () => ({ useAuth: () => mockUseAuth() }));

const STAGES: PsStage[] = [
  { id: "s1", name: "Преговори", category: "work", sort: 0 },
  { id: "s2", name: "Договор", category: "work", sort: 1 },
];

/** Every dialog (business-os PropertyFlow task's `<dialog>`-based Dialog
 * component) is always mounted, regardless of `open` - jsdom, unlike a real
 * browser, does not apply the UA `dialog:not([open]) { display: none }`
 * rule, so a closed dialog's <option>/<label> text is still visible to
 * Testing Library queries. Scoping to the one dialog that actually has the
 * `open` attribute (set by the real `showModal()` call) avoids matching a
 * client's name inside NewAssignmentDialog's always-present <select>, etc. */
function currentDialog(): HTMLElement {
  const dialog = document.querySelector("dialog[open]");
  if (!dialog) throw new Error("no open dialog found");
  return dialog as HTMLElement;
}

/** Client/assignment list rows are buttons whose accessible name also
 * includes badge/date text, so `getByRole("button", { name })` is brittle;
 * matching the exact label text (unambiguous once excluding hidden dialog
 * content by clicking the ancestor button) is more robust. */
async function clickCard(user: ReturnType<typeof userEvent.setup>, text: string) {
  const matches = await screen.findAllByText(text);
  const button = matches.map((el) => el.closest("button")).find((b): b is HTMLButtonElement => b !== null);
  if (!button) throw new Error(`no clickable card found for "${text}"`);
  await user.click(button);
}

/** A small, stateful fake backend - mutated by mockPost, read by mockGet -
 * so the create/complete/stage/deadline flows exercise the real request/
 * response/cache-invalidation round trip rather than only the initial
 * render, matching this codebase's existing integration-test convention. */
function setUpFakeBackend({
  clients, assignments, actions,
}: { clients: PsClient[]; assignments: PsAssignment[]; actions: PsNextAction[] }) {
  const state = { clients, assignments, actions, history: {} as Record<string, PsDeadlineChange[]>, nextId: 1 };

  mockGet.mockImplementation((path: string) => {
    if (path === "/ps/clients") return Promise.resolve(state.clients);
    if (path === "/ps/assignments") return Promise.resolve(state.assignments);
    if (path === "/ps/next-actions") return Promise.resolve(state.actions);
    if (path === "/ps/workflow-templates") return Promise.resolve([]);
    if (path === "/users") return Promise.resolve([{ id: "u1", name: "Мария" }]);
    const stagesMatch = /^\/ps\/assignments\/([^/]+)\/stages$/.exec(path);
    if (stagesMatch) return Promise.resolve(STAGES);
    const historyMatch = /^\/ps\/assignments\/([^/]+)\/deadline-history$/.exec(path);
    if (historyMatch) return Promise.resolve(state.history[historyMatch[1]] ?? []);
    return Promise.reject(new Error(`unexpected GET ${path}`));
  });

  mockPost.mockImplementation((path: string, body: Record<string, unknown>) => {
    if (path === "/ps/clients") {
      const client: PsClient = { id: `new-client-${state.nextId++}`, name: body.name as string, kind: body.kind as PsClient["kind"] };
      state.clients = [...state.clients, client];
      return Promise.resolve(client);
    }
    if (path === "/ps/assignments") {
      const assignment: PsAssignment = {
        id: `new-assignment-${state.nextId++}`, client_id: body.client_id as string, title: body.title as string,
        lifecycle_state: "active", current_stage: null, official_deadline_on: null,
        internal_target_on: null, current_deadline_risk: "none", current_stale: false,
      };
      state.assignments = [...state.assignments, assignment];
      return Promise.resolve(assignment);
    }
    if (path === "/ps/next-actions") {
      const action: PsNextAction = {
        id: `new-action-${state.nextId++}`, assignment_id: body.assignment_id as string, title: body.title as string,
        owner_user_id: body.owner_user_id as string, due_on: body.due_on as string, completed: false, risk: "ok",
      };
      state.actions = [...state.actions, action];
      return Promise.resolve(action);
    }
    const completeMatch = /^\/ps\/next-actions\/([^/]+)\/complete$/.exec(path);
    if (completeMatch) {
      state.actions = state.actions.map((a) => (a.id === completeMatch[1] ? { ...a, completed: true } : a));
      return Promise.resolve({ ok: true });
    }
    const stageMatch = /^\/ps\/assignments\/([^/]+)\/stage$/.exec(path);
    if (stageMatch) {
      const stage = STAGES.find((s) => s.id === body.to_stage_id) ?? null;
      state.assignments = state.assignments.map((a) => (a.id === stageMatch[1] ? { ...a, current_stage: stage } : a));
      return Promise.resolve(state.assignments.find((a) => a.id === stageMatch[1]));
    }
    const deadlineMatch = /^\/ps\/assignments\/([^/]+)\/deadline$/.exec(path);
    if (deadlineMatch) {
      const id = deadlineMatch[1];
      state.assignments = state.assignments.map((a) => (a.id === id ? { ...a, official_deadline_on: body.official_deadline_on as string } : a));
      state.history[id] = [
        ...(state.history[id] ?? []),
        { old_value: null, new_value: body.official_deadline_on as string, reason: body.reason as string, changed_at: "2026-08-01T00:00:00Z" },
      ];
      return Promise.resolve(state.assignments.find((a) => a.id === id));
    }
    return Promise.reject(new Error(`unexpected POST ${path}`));
  });

  return state;
}

function renderPsPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/ps"]}>
        <PsPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("PsPage", () => {
  beforeEach(() => {
    mockGet.mockReset();
    mockPost.mockReset();
    mockUseAuth.mockReturnValue({ me: { user_id: "u1", name: "Мария" } });
  });

  it("selecting a client shows their engagements; selecting an engagement shows its next actions and detail panel", async () => {
    setUpFakeBackend({
      clients: [{ id: "c1", name: "Иван Петров", kind: "person" }],
      assignments: [{
        id: "a1", client_id: "c1", title: "Продажба апартамент", lifecycle_state: "active",
        current_stage: STAGES[0], official_deadline_on: "2026-09-01", internal_target_on: null,
        current_deadline_risk: "normal", current_stale: false,
      }],
      actions: [{
        id: "n1", assignment_id: "a1", title: "Изпрати оферта", owner_user_id: "u1",
        due_on: "2026-08-10", completed: false, risk: "attention",
      }],
    });
    renderPsPage();
    const user = userEvent.setup();

    await clickCard(user, "Иван Петров");
    await screen.findByText("Продажба апартамент");
    await clickCard(user, "Продажба апартамент");

    // Appears twice by design: once in the "Следваща задача" summary, once
    // in the open-tasks list below it.
    await waitFor(() => expect(screen.getAllByText("Изпрати оферта").length).toBeGreaterThan(0));
    expect(screen.getByRole("heading", { name: "Продажба апартамент" })).toBeInTheDocument();
    expect(screen.getByText("2026-09-01")).toBeInTheDocument();
  });

  it("creates a new client via the dialog and shows it in the list", async () => {
    const state = setUpFakeBackend({ clients: [], assignments: [], actions: [] });
    renderPsPage();
    const user = userEvent.setup();

    await user.click(screen.getByText("+ Нов клиент"));
    await user.type(within(currentDialog()).getByLabelText("Име"), "Нов Клиент");
    await user.click(within(currentDialog()).getByRole("button", { name: "Добави клиент" }));

    await waitFor(() => expect(mockPost).toHaveBeenCalledWith("/ps/clients", { name: "Нов Клиент", kind: "person" }));
    await waitFor(() => {
      const matches = screen.getAllByText("Нов Клиент");
      expect(matches.some((el) => el.closest("button"))).toBe(true);
    });
    expect(state.clients).toHaveLength(1);
  });

  it("creates a new assignment for the selected client and auto-selects it", async () => {
    setUpFakeBackend({
      clients: [{ id: "c1", name: "Иван Петров", kind: "person" }], assignments: [], actions: [],
    });
    renderPsPage();
    const user = userEvent.setup();

    await clickCard(user, "Иван Петров");
    await user.click(screen.getAllByText("+ Нова поръчка")[0]);
    await user.type(within(currentDialog()).getByLabelText("Заглавие"), "Нов ангажимент");
    await user.click(within(currentDialog()).getByRole("button", { name: "Добави поръчка" }));

    await waitFor(() => expect(mockPost).toHaveBeenCalledWith("/ps/assignments", {
      client_id: "c1", title: "Нов ангажимент", workflow_template_id: null,
    }));
    expect(await screen.findByRole("heading", { name: "Нов ангажимент" })).toBeInTheDocument();
  });

  it("completing a next action moves it into the collapsible completed section", async () => {
    setUpFakeBackend({
      clients: [{ id: "c1", name: "Иван Петров", kind: "person" }],
      assignments: [{
        id: "a1", client_id: "c1", title: "Ангажимент", lifecycle_state: "active",
        current_stage: null, official_deadline_on: null, internal_target_on: null,
        current_deadline_risk: "none", current_stale: false,
      }],
      actions: [{
        id: "n1", assignment_id: "a1", title: "Изпрати оферта", owner_user_id: "u1",
        due_on: "2026-08-10", completed: false, risk: "attention",
      }],
    });
    renderPsPage();
    const user = userEvent.setup();

    await clickCard(user, "Иван Петров");
    await clickCard(user, "Ангажимент");
    await user.click(await screen.findByLabelText("Отбележи като завършено"));

    await waitFor(() => expect(mockPost).toHaveBeenCalledWith("/ps/next-actions/n1/complete"));
    expect(await screen.findByText("Покажи приключените (1)")).toBeInTheDocument();
    expect(screen.getByText("Няма задачи.")).toBeInTheDocument();
  });

  it("changes an assignment's stage via the stage-change dialog", async () => {
    setUpFakeBackend({
      clients: [{ id: "c1", name: "Иван Петров", kind: "person" }],
      assignments: [{
        id: "a1", client_id: "c1", title: "Ангажимент", lifecycle_state: "active",
        current_stage: STAGES[0], official_deadline_on: null, internal_target_on: null,
        current_deadline_risk: "none", current_stale: false,
      }],
      actions: [],
    });
    renderPsPage();
    const user = userEvent.setup();

    await clickCard(user, "Иван Петров");
    await clickCard(user, "Ангажимент");
    await user.click(await screen.findByRole("button", { name: "Промени етап" }));
    await user.selectOptions(within(currentDialog()).getByRole("combobox"), "Договор");
    await user.click(within(currentDialog()).getByRole("button", { name: "Запази" }));

    await waitFor(() => expect(mockPost).toHaveBeenCalledWith("/ps/assignments/a1/stage", { to_stage_id: "s2" }));
    await waitFor(() => {
      const badges = screen.getAllByText("Договор");
      expect(badges.length).toBeGreaterThan(0);
    });
  });

  it("disables the stage-change button, with a clear explanation, for an assignment with no stages", async () => {
    mockGet.mockImplementation((path: string) => {
      if (path === "/ps/clients") {
        return Promise.resolve([{ id: "c1", name: "Иван Петров", kind: "person" }]);
      }
      if (path === "/ps/assignments") {
        return Promise.resolve([{
          id: "a1", client_id: "c1", title: "Консултация", lifecycle_state: "active",
          current_stage: null, official_deadline_on: null, internal_target_on: null,
          current_deadline_risk: "none", current_stale: false,
        }]);
      }
      if (path === "/ps/next-actions") return Promise.resolve([]);
      if (path === "/ps/workflow-templates") return Promise.resolve([]);
      if (path === "/users") return Promise.resolve([]);
      if (/^\/ps\/assignments\/[^/]+\/stages$/.exec(path)) return Promise.resolve([]);
      return Promise.reject(new Error(`unexpected GET ${path}`));
    });
    renderPsPage();
    const user = userEvent.setup();

    await clickCard(user, "Иван Петров");
    await clickCard(user, "Консултация");

    const button = await screen.findByRole("button", { name: "Промени етап" });
    await waitFor(() => expect(button).toBeDisabled());
    expect(button).toHaveAttribute(
      "title", "Поръчката няма зададени етапи — създадена е без работен процес.",
    );
  });

  it("hides the workflow-templates link for a non-owner", async () => {
    setUpFakeBackend({ clients: [], assignments: [], actions: [] });
    renderPsPage();

    await screen.findByText("Табло");
    expect(screen.queryByRole("link", { name: "Работни процеси" })).not.toBeInTheDocument();
  });

  it("shows the workflow-templates link for an Owner, pointing at the settings route", async () => {
    mockUseAuth.mockReturnValue({ me: { user_id: "u1", name: "Мария", is_owner: true } });
    setUpFakeBackend({ clients: [], assignments: [], actions: [] });
    renderPsPage();

    const link = await screen.findByRole("link", { name: "Работни процеси" });
    expect(link).toHaveAttribute("href", "/ps/workflow-templates");
  });

  it("regression: switching to a client with fewer engagements than the current page resets pagination instead of showing an empty list", async () => {
    const manyAssignments: PsAssignment[] = Array.from({ length: PAGE_SIZE + 2 }, (_, i) => ({
      id: `a${i}`, client_id: "big", title: `Ангажимент ${i}`, lifecycle_state: "active",
      current_stage: null, official_deadline_on: null, internal_target_on: null,
      current_deadline_risk: "none", current_stale: false,
    }));
    setUpFakeBackend({
      clients: [
        { id: "big", name: "Голям Клиент", kind: "company" },
        { id: "small", name: "Малък Клиент", kind: "person" },
      ],
      assignments: [
        ...manyAssignments,
        { id: "s1", client_id: "small", title: "Единствен ангажимент", lifecycle_state: "active",
          current_stage: null, official_deadline_on: null, internal_target_on: null,
          current_deadline_risk: "none", current_stale: false },
      ],
      actions: [],
    });
    renderPsPage();
    const user = userEvent.setup();

    await clickCard(user, "Голям Клиент");
    await screen.findByText("Ангажимент 0");
    await user.click(screen.getByLabelText("Следваща страница"));
    await screen.findByText(`Ангажимент ${PAGE_SIZE}`);

    await clickCard(user, "Малък Клиент");

    expect(await screen.findByText("Единствен ангажимент")).toBeInTheDocument();
    expect(screen.queryByText("Няма поръчки.")).not.toBeInTheDocument();
  });

  it("regression: reopening the deadline dialog for a different engagement shows that engagement's own deadline, not the previous one's", async () => {
    setUpFakeBackend({
      clients: [{ id: "c1", name: "Иван Петров", kind: "person" }],
      assignments: [
        { id: "a1", client_id: "c1", title: "Първи ангажимент", lifecycle_state: "active",
          current_stage: null, official_deadline_on: "2026-01-15", internal_target_on: null,
          current_deadline_risk: "none", current_stale: false },
        { id: "a2", client_id: "c1", title: "Втори ангажимент", lifecycle_state: "active",
          current_stage: null, official_deadline_on: null, internal_target_on: null,
          current_deadline_risk: "none", current_stale: false },
      ],
      actions: [],
    });
    renderPsPage();
    const user = userEvent.setup();

    await clickCard(user, "Иван Петров");
    await clickCard(user, "Първи ангажимент");
    await user.click(await screen.findByText("Промени срок"));
    const firstDialogDate = currentDialog().querySelector('input[type="date"]') as HTMLInputElement;
    expect(firstDialogDate.value).toBe("2026-01-15");
    await user.click(within(currentDialog()).getByText("Отказ"));

    await clickCard(user, "Втори ангажимент");
    await user.click(await screen.findByText("Промени срок"));
    const secondDialogDate = currentDialog().querySelector('input[type="date"]') as HTMLInputElement;
    expect(secondDialogDate.value).toBe("");
  });
});
