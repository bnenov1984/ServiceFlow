import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "../lib/api";
import { WorkflowTemplatesPage } from "./WorkflowTemplatesPage";

const mockGet = vi.fn();
const mockPost = vi.fn();
const mockPut = vi.fn();
vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../lib/api")>("../lib/api");
  return {
    ...actual,
    api: {
      ...actual.api,
      get: (...args: unknown[]) => mockGet(...args),
      post: (...args: unknown[]) => mockPost(...args),
      put: (...args: unknown[]) => mockPut(...args),
    },
  };
});

const mockUseAuth = vi.fn();
vi.mock("../auth/AuthContext", () => ({ useAuth: () => mockUseAuth() }));

const OWNER_ME = { user_id: "u1", name: "Мария", is_owner: true };

const TEMPLATE = {
  id: "t1", name: "Оценка на имот", is_active: true,
  stages: [
    { id: "s1", name: "Оглед", category: "work", sort: 0 },
    { id: "s2", name: "Предаване", category: "delivery", sort: 1 },
  ],
};

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/ps/workflow-templates"]}>
        <WorkflowTemplatesPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("WorkflowTemplatesPage", () => {
  beforeEach(() => {
    mockGet.mockReset();
    mockPost.mockReset();
    mockPut.mockReset();
    mockUseAuth.mockReturnValue({ me: OWNER_ME });
  });

  it("shows an access-denied state for a non-owner, with no request made", () => {
    mockUseAuth.mockReturnValue({ me: { user_id: "u2", name: "Работник", is_owner: false } });
    renderPage();

    expect(screen.getByText("Само собственикът може да направи това.")).toBeInTheDocument();
    expect(mockGet).not.toHaveBeenCalled();
  });

  it("shows an empty state when there are no templates", async () => {
    mockGet.mockResolvedValue([]);
    renderPage();

    expect(await screen.findByText("Няма създадени работни процеси.")).toBeInTheDocument();
  });

  it("lists existing templates with their stage names", async () => {
    mockGet.mockResolvedValue([TEMPLATE]);
    renderPage();

    expect(await screen.findByText("Оценка на имот")).toBeInTheDocument();
    expect(screen.getByText("Оглед → Предаване")).toBeInTheDocument();
  });

  it("opens a blank create form with one empty stage row", async () => {
    mockGet.mockResolvedValue([]);
    renderPage();
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "+ Нов работен процес" }));

    expect(screen.getByLabelText("Име")).toHaveValue("");
    expect(screen.getAllByPlaceholderText("Име на етап…")).toHaveLength(1);
    expect(screen.getByRole("button", { name: "Запази" })).toBeDisabled();
  });

  it("blocks submission until name and every stage name are filled", async () => {
    mockGet.mockResolvedValue([]);
    renderPage();
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "+ Нов работен процес" }));
    const saveButton = screen.getByRole("button", { name: "Запази" });
    expect(saveButton).toBeDisabled();

    await user.type(screen.getByLabelText("Име"), "Нов процес");
    expect(saveButton).toBeDisabled();

    await user.type(screen.getByPlaceholderText("Име на етап…"), "Първи етап");
    expect(saveButton).not.toBeDisabled();
    expect(mockPost).not.toHaveBeenCalled();
  });

  it("adds, reorders and removes stage rows", async () => {
    mockGet.mockResolvedValue([]);
    renderPage();
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "+ Нов работен процес" }));
    await user.type(screen.getByPlaceholderText("Име на етап…"), "А");
    await user.click(screen.getByRole("button", { name: "+ Добави етап" }));

    const nameInputs = screen.getAllByPlaceholderText("Име на етап…");
    expect(nameInputs).toHaveLength(2);
    await user.type(nameInputs[1], "Б");

    await user.click(screen.getAllByRole("button", { name: "Премести надолу" })[0]);
    expect(screen.getAllByPlaceholderText("Име на етап…").map((el) => (el as HTMLInputElement).value))
      .toEqual(["Б", "А"]);

    await user.click(screen.getAllByRole("button", { name: "Премахни етап" })[0]);
    expect(screen.getAllByPlaceholderText("Име на етап…")).toHaveLength(1);
  });

  it("submits a new template with the exact expected payload", async () => {
    mockGet.mockResolvedValue([]);
    mockPost.mockResolvedValue({ ...TEMPLATE, id: "t2" });
    renderPage();
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "+ Нов работен процес" }));
    await user.type(screen.getByLabelText("Име"), "Продажба на имот");
    await user.type(screen.getByPlaceholderText("Име на етап…"), "Оглед");
    await user.selectOptions(screen.getByLabelText("Категория"), "delivery");
    await user.click(screen.getByRole("button", { name: "Запази" }));

    await waitFor(() => expect(mockPost).toHaveBeenCalledWith("/ps/workflow-templates", {
      name: "Продажба на имот",
      stages: [{ name: "Оглед", category: "delivery" }],
    }));
  });

  it("opens a pre-filled edit form and submits a PUT to the exact template path", async () => {
    mockGet.mockResolvedValue([TEMPLATE]);
    mockPut.mockResolvedValue(TEMPLATE);
    renderPage();
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "Редактирай" }));

    expect(screen.getByLabelText("Име")).toHaveValue("Оценка на имот");
    const nameInputs = screen.getAllByPlaceholderText("Име на етап…") as HTMLInputElement[];
    expect(nameInputs.map((i) => i.value)).toEqual(["Оглед", "Предаване"]);

    await user.clear(screen.getByLabelText("Име"));
    await user.type(screen.getByLabelText("Име"), "Оценка на имот (преработена)");
    await user.click(screen.getByRole("button", { name: "Запази" }));

    await waitFor(() => expect(mockPut).toHaveBeenCalledWith("/ps/workflow-templates/t1", {
      name: "Оценка на имот (преработена)",
      stages: [{ name: "Оглед", category: "work" }, { name: "Предаване", category: "delivery" }],
    }));
  });

  it("invalidates the workflow-templates query on successful save and closes the form", async () => {
    mockGet.mockResolvedValue([]);
    mockPost.mockResolvedValue(TEMPLATE);
    renderPage();
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "+ Нов работен процес" }));
    // Initial mount already issued one GET; a fresh count from here isolates
    // the invalidation-triggered refetch this test is actually about.
    mockGet.mockClear();
    await user.type(screen.getByLabelText("Име"), "X");
    await user.type(screen.getByPlaceholderText("Име на етап…"), "Y");
    await user.click(screen.getByRole("button", { name: "Запази" }));

    // The list query has an active observer, so invalidation triggers an
    // immediate refetch (a second GET) rather than leaving isInvalidated set.
    await waitFor(() => expect(mockGet).toHaveBeenCalledTimes(1));
    expect(screen.queryByLabelText("Име")).not.toBeInTheDocument();
  });

  it("shows a recoverable inline error on failure, keeping the form open", async () => {
    mockGet.mockResolvedValue([]);
    mockPost.mockRejectedValue(new ApiError(400, "template_create_failed", "errors.ps.template_needs_stages"));
    renderPage();
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "+ Нов работен процес" }));
    await user.type(screen.getByLabelText("Име"), "X");
    await user.type(screen.getByPlaceholderText("Име на етап…"), "Y");
    await user.click(screen.getByRole("button", { name: "Запази" }));

    expect(await screen.findByText("Работният процес трябва да има поне един етап.")).toBeInTheDocument();
    expect(screen.getByLabelText("Име")).toBeInTheDocument();
  });

  it("prevents a duplicate submit from a rapid double-click", async () => {
    mockGet.mockResolvedValue([]);
    let resolvePost: (v: unknown) => void = () => {};
    mockPost.mockReturnValue(new Promise((resolve) => { resolvePost = resolve; }));
    renderPage();
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "+ Нов работен процес" }));
    await user.type(screen.getByLabelText("Име"), "X");
    await user.type(screen.getByPlaceholderText("Име на етап…"), "Y");
    const saveButton = screen.getByRole("button", { name: "Запази" });
    await user.click(saveButton);
    await user.click(saveButton);

    resolvePost(TEMPLATE);
    await waitFor(() => expect(mockPost).toHaveBeenCalledTimes(1));
  });

  it("cancelling the form makes no API call", async () => {
    mockGet.mockResolvedValue([]);
    renderPage();
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "+ Нов работен процес" }));
    await user.type(screen.getByLabelText("Име"), "X");
    await user.click(screen.getByRole("button", { name: "Отказ" }));

    expect(screen.queryByLabelText("Име")).not.toBeInTheDocument();
    expect(mockPost).not.toHaveBeenCalled();
  });
});
