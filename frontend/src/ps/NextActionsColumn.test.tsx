import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { NextActionsColumn } from "./NextActionsColumn";
import type { PsAssignment, PsNextAction, PsUser } from "./types";

vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../lib/api")>("../lib/api");
  return { ...actual, api: { ...actual.api, post: vi.fn() } };
});

// NextActionsColumn always mounts NewActionDialog (closed by default), which
// calls useAuth() to default the owner field — needs a provider even though
// no test here opens the dialog.
vi.mock("../auth/AuthContext", () => ({
  useAuth: () => ({ me: { user_id: "u1", name: "Мария", is_owner: true } }),
}));

const ASSIGNMENT: PsAssignment = {
  id: "a1", client_id: "c1", title: "Продажба апартамент", lifecycle_state: "active",
  current_stage: null, official_deadline_on: null, internal_target_on: null,
  current_deadline_risk: "none", current_stale: false,
};

const USERS: PsUser[] = [{ id: "u1", name: "Мария Георгиева" }];

function renderColumn(assignment: PsAssignment | null, actions: PsNextAction[]) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
      <NextActionsColumn
        assignment={assignment}
        actions={actions}
        users={USERS}
        isLoading={false}
        isError={false}
        errorText=""
        onRetry={() => {}}
      />
    </QueryClientProvider>,
  );
}

describe("NextActionsColumn — next-task summary", () => {
  it("shows a compact 'Следваща задача' block with title, due date and owner for the earliest open task", () => {
    renderColumn(ASSIGNMENT, [
      {
        id: "n1", assignment_id: "a1", title: "Подпис на договор", owner_user_id: "u1",
        due_on: "2026-09-01", completed: false, risk: "ok",
      },
      {
        id: "n2", assignment_id: "a1", title: "По-късна задача", owner_user_id: "u1",
        due_on: "2026-09-15", completed: false, risk: "ok",
      },
    ]);

    expect(screen.getByText("Следваща задача")).toBeInTheDocument();
    expect(screen.getAllByText("Подпис на договор").length).toBeGreaterThan(0);
    expect(screen.getAllByText("2026-09-01").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Мария Георгиева").length).toBeGreaterThan(0);
  });
});

describe("NextActionsColumn — no-next-task state", () => {
  it("hides the summary block when every task is already completed", () => {
    renderColumn(ASSIGNMENT, [
      { id: "n1", assignment_id: "a1", title: "Готова задача", owner_user_id: "u1", due_on: "2026-09-01", completed: true, risk: "done" },
    ]);

    expect(screen.queryByText("Следваща задача")).not.toBeInTheDocument();
  });

  it("hides the summary block when the order has no tasks at all", () => {
    renderColumn(ASSIGNMENT, []);
    expect(screen.queryByText("Следваща задача")).not.toBeInTheDocument();
  });

  it("hides the summary block when no order is selected", () => {
    renderColumn(null, []);
    expect(screen.queryByText("Следваща задача")).not.toBeInTheDocument();
  });
});

describe("NextActionsColumn — task/stage visual separation", () => {
  it("renders an open task with a 20×20 checkbox, title, owner and due date", () => {
    renderColumn(ASSIGNMENT, [
      { id: "n1", assignment_id: "a1", title: "Огледна карта", owner_user_id: "u1", due_on: "2026-09-01", completed: false, risk: "attention" },
    ]);

    const checkbox = screen.getByRole("checkbox", { name: "Отбележи като завършено" });
    expect(checkbox).toHaveClass("h-5", "w-5");
    expect(screen.getAllByText("Огледна карта").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Мария Георгиева").length).toBeGreaterThan(0);
    expect(screen.getByText("Внимание")).toBeInTheDocument();
  });
});
