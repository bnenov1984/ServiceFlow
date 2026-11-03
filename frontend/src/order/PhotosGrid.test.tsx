import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../lib/api";
import { PhotosGrid } from "./PhotosGrid";

vi.mock("../lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../lib/api")>();
  return { ...actual, api: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), put: vi.fn(), delete: vi.fn() } };
});

beforeEach(() => {
  vi.mocked(api.get).mockReset();
  vi.mocked(api.post).mockReset();
});

const PHOTO = {
  id: "a1", kind: "photo" as const, stage: "reception", caption: "", mime: "image/jpeg",
  has_thumbnail: true, display_name: "2026-00049_1.jpg",
};

function renderGrid(attachments: (typeof PHOTO)[] = [PHOTO]) {
  vi.mocked(api.get).mockResolvedValue(attachments);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <PhotosGrid orderId="order-1" />
    </QueryClientProvider>,
  );
}

describe("PhotosGrid — WP-E #10/#11 (capture buttons, display name)", () => {
  it("shows explicit camera and gallery buttons instead of a generic upload button", async () => {
    renderGrid();
    expect(await screen.findByRole("button", { name: /Снимай/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /От устройството/ })).toBeInTheDocument();
  });

  it("uploads a file selected via the gallery input to the active stage", async () => {
    const user = userEvent.setup();
    vi.mocked(api.post).mockResolvedValue({ ...PHOTO, id: "a2" });
    renderGrid([]);
    await screen.findByRole("button", { name: /От устройството/ });
    const galleryInput = document.querySelectorAll('input[type="file"]')[1] as HTMLInputElement;
    const file = new File(["x"], "photo.jpg", { type: "image/jpeg" });

    await user.upload(galleryInput, file);

    expect(api.post).toHaveBeenCalledWith("/orders/order-1/attachments", expect.any(FormData));
  });

  it("shows the attachment's display name as the lightbox caption", async () => {
    const user = userEvent.setup();
    renderGrid();
    const thumb = await screen.findByAltText("Снимки");

    await user.click(thumb.closest("button") as HTMLElement);

    expect(await screen.findByText("2026-00049_1.jpg")).toBeInTheDocument();
  });
});
