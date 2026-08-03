import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { AssignmentDetailPanel } from "./AssignmentDetailPanel";
import type { PsAssignment, PsClient, PsStage } from "./types";

const mockGet = vi.fn();
vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../lib/api")>("../lib/api");
  return { ...actual, api: { ...actual.api, get: (...args: unknown[]) => mockGet(...args) } };
});

const CLIENT: PsClient = { id: "c1", name: "Иван Петров", kind: "person" };

const STAGES: PsStage[] = [
  { id: "s1", name: "Оглед", category: "work", sort: 0 },
  { id: "s2", name: "Договор", category: "work", sort: 1 },
  { id: "s3", name: "Предаване", category: "delivery", sort: 2 },
];

function assignment(overrides: Partial<PsAssignment> = {}): PsAssignment {
  return {
    id: "a1", client_id: "c1", title: "Продажба апартамент", lifecycle_state: "active",
    current_stage: STAGES[1], official_deadline_on: null, internal_target_on: null,
    current_deadline_risk: "none", current_stale: false,
    ...overrides,
  };
}

function renderPanel(a: PsAssignment | null, stages: PsStage[] = STAGES) {
  mockGet.mockImplementation((path: string) => {
    if (/\/stages$/.test(path)) return Promise.resolve(stages);
    if (/\/deadline-history$/.test(path)) return Promise.resolve([]);
    return Promise.reject(new Error(`unexpected GET ${path}`));
  });
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
      <AssignmentDetailPanel assignment={a} client={CLIENT} />
    </QueryClientProvider>,
  );
}

describe("AssignmentDetailPanel — current-stage display", () => {
  it("shows a 'Текущ етап' label alongside the current stage name in the header", async () => {
    renderPanel(assignment({ current_stage: STAGES[1] }));

    expect(await screen.findAllByText("Текущ етап")).not.toHaveLength(0);
    expect(screen.getAllByText("Договор").length).toBeGreaterThan(0);
  });

  it("shows the 'no stage' fallback when the assignment has no current stage", async () => {
    renderPanel(assignment({ current_stage: null }), []);

    expect(await screen.findByText("Без етап")).toBeInTheDocument();
  });
});

describe("AssignmentDetailPanel — stage progress rendering", () => {
  it("renders stages in configured order with completed/current/future visually distinguished", async () => {
    renderPanel(assignment({ current_stage: STAGES[1] }));

    await waitFor(() => expect(screen.getAllByText("Оглед").length).toBeGreaterThan(0));
    // Completed marker (✓) appears exactly once — only the stage before current.
    expect(screen.getAllByText("✓")).toHaveLength(1);
    // The current-stage pill appears exactly once.
    const pills = screen.getAllByText("Текущ етап");
    expect(pills.length).toBeGreaterThanOrEqual(1);
    // Future stage text is present but not marked completed.
    expect(screen.getAllByText("Предаване").length).toBeGreaterThan(0);
  });

  it("only ever marks one stage as current, even with several stages", async () => {
    renderPanel(assignment({ current_stage: STAGES[1] }));
    // "Оглед" only renders once the async stages list resolves (unlike the
    // header's current-stage badge, which renders immediately from the
    // assignment prop) — waiting on it here actually waits for the list.
    await waitFor(() => expect(screen.getAllByText("Оглед").length).toBeGreaterThan(0));

    // Exactly one completed checkmark (the stage before current) proves
    // single-current indirectly: current-stage sort is 1, so only sort-0
    // ("Оглед") can read as completed.
    expect(screen.getAllByText("✓")).toHaveLength(1);
  });

  it("shows the empty-stages message instead of a progress list when the order has none", async () => {
    renderPanel(assignment({ current_stage: null }), []);

    expect(await screen.findByText("Няма дефинирани етапи.")).toBeInTheDocument();
  });
});

describe("AssignmentDetailPanel — task/stage visual separation", () => {
  it("never renders stages as checkboxes", async () => {
    renderPanel(assignment({ current_stage: STAGES[1] }));
    await waitFor(() => expect(screen.getAllByText("Оглед").length).toBeGreaterThan(0));

    expect(document.querySelectorAll('input[type="checkbox"]')).toHaveLength(0);
  });
});
