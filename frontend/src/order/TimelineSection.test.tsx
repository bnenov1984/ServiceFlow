import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { api } from "../lib/api";
import { TimelineSection } from "./TimelineSection";

vi.mock("../lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../lib/api")>();
  return { ...actual, api: { ...actual.api, get: vi.fn() } };
});

function renderTimeline(events: object[]) {
  vi.mocked(api.get).mockImplementation((path: string) => {
    if (path.endsWith("/timeline")) return Promise.resolve(events) as never;
    if (path.startsWith("/users")) return Promise.resolve([{ id: "u1", name: "Мария" }]) as never;
    return Promise.reject(new Error(`unexpected GET ${path}`));
  });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <TimelineSection orderId="order-1" />
    </QueryClientProvider>,
  );
}

describe("TimelineSection (Wave 2 Issue 34)", () => {
  it("shows a contact event's actual type badge and summary, not a generic label", async () => {
    renderTimeline([{
      event_type: "note_or_contact_recorded", actor_user_id: "u1",
      data: { type: "call", summary: "Обадих се на клиента за резервните части" },
      created_at: "2026-03-15T10:00:00Z",
    }]);

    expect(await screen.findByText("Обаждане")).toBeInTheDocument();
    expect(screen.getByText("Обадих се на клиента за резервните части")).toBeInTheDocument();
  });

  it("renders a historical message/visit-type event's badge correctly too", async () => {
    renderTimeline([{
      event_type: "note_or_contact_recorded", actor_user_id: "u1",
      data: { type: "visit", summary: "Дойде да пита за напредъка" },
      created_at: "2026-03-15T10:00:00Z",
    }]);

    expect(await screen.findByText("На място")).toBeInTheDocument();
    expect(screen.getByText("Дойде да пита за напредъка")).toBeInTheDocument();
  });

  it("still renders the generic label for non-contact events", async () => {
    renderTimeline([{
      event_type: "status_changed", actor_user_id: "u1",
      data: { from: "received", to: "diagnostics" },
      created_at: "2026-03-15T10:00:00Z",
    }]);

    expect(await screen.findByText("Статусът е променен")).toBeInTheDocument();
  });

  // invoice-order-linking checkpoint 2 — a real gap caught in manual QA: this
  // event type was added to the backend's KNOWN_EVENT_TYPES allowlist in
  // checkpoint 1, but EVENT_LABEL was never updated, so it rendered as the
  // raw "invoice_linked" string instead of Bulgarian text.
  it("renders the Bulgarian label for invoice_linked, not the raw event type", async () => {
    renderTimeline([{
      event_type: "invoice_linked", actor_user_id: "u1",
      data: { invoice_id: "inv-1" },
      created_at: "2026-03-15T10:00:00Z",
    }]);

    expect(await screen.findByText("Фактурата е свързана с поръчката")).toBeInTheDocument();
    expect(screen.queryByText("invoice_linked")).not.toBeInTheDocument();
  });
});
