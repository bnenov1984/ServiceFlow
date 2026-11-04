import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { OrderStep, type OrderStepValue } from "./OrderStep";

// Q9/Q10 (WP-D): OrderStep fetches GET /assets/{id}/service-history for the
// mileage floor whenever assetTypeCode === "vehicle" — default mock has no
// floor (current_mileage: null), the pre-existing "no constraint at all"
// shape every test below except the dedicated WP-D describe block relies on.
const mockServiceHistory = vi.fn();
vi.mock("../lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../lib/api")>();
  return {
    ...actual,
    api: {
      ...actual.api,
      get: vi.fn((path: string) => {
        if (path.includes("/service-history")) return Promise.resolve(mockServiceHistory());
        return Promise.resolve([]);
      }),
    },
  };
});

// OrderStep reads me?.is_owner for the Q10 bypass — same mock-module
// pattern InvoiceCard.test.tsx already uses for useAuth.
const mockUseAuth = vi.fn();
vi.mock("../auth/AuthContext", () => ({
  useAuth: () => mockUseAuth(),
}));

const DEFAULT_VALUE: OrderStepValue = {
  complaint: "", accessories: [], photos: [], partLines: [],
  priority: "normal", technicianId: null, mileage: "",
  mileageConfirmedLower: false, mileageOverrideComment: "",
  deliveryMethod: "pickup", deliveryAddress: "",
};

// A real controlled wrapper (useState, not a mock) so add/remove actions
// actually re-render OrderStep with the updated draft, the same way
// IntakePage drives it for real.
function Harness({
  initial = DEFAULT_VALUE, assetTypeCode = "phone", defaultDeliveryAddress = null,
}: {
  initial?: OrderStepValue; assetTypeCode?: string; defaultDeliveryAddress?: string | null;
}) {
  const [value, setValue] = useState(initial);
  return (
    <OrderStep
      value={value}
      assetId="asset-1"
      assetTypeCode={assetTypeCode}
      defaultDeliveryAddress={defaultDeliveryAddress}
      onChange={setValue}
      onSubmit={vi.fn()}
      submitting={false}
      error={null}
    />
  );
}

function renderStep(
  initial?: OrderStepValue, assetTypeCode?: string, defaultDeliveryAddress?: string | null,
  isOwner = false,
) {
  mockUseAuth.mockReturnValue({ me: { is_owner: isOwner } });
  mockServiceHistory.mockReturnValue({ current_mileage: null });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <Harness
        initial={initial} assetTypeCode={assetTypeCode}
        defaultDeliveryAddress={defaultDeliveryAddress}
      />
    </QueryClientProvider>,
  );
  // The "Добави" accessible name is reused by AccessoriesChecklist's own add
  // button on this same screen — scope every query to the parts section's
  // own container so the two never collide.
  return within(screen.getByText("Части (по избор)").closest("div") as HTMLElement);
}

describe("OrderStep — Issue 25 (no promised date at intake)", () => {
  it("does not render a promised-date field any more", () => {
    renderStep();
    expect(screen.queryByText("Обещана дата")).not.toBeInTheDocument();
  });
});

describe("OrderStep — Wave 3 Issues 21/26/27 (mileage at intake)", () => {
  it("shows the mileage field for a vehicle order", () => {
    renderStep(undefined, "vehicle");
    expect(screen.getByText("Пробег (км)")).toBeInTheDocument();
  });

  it("does not show the mileage field for a non-vehicle order", () => {
    renderStep(undefined, "phone");
    expect(screen.queryByText("Пробег (км)")).not.toBeInTheDocument();
  });

  it("typing a mileage value updates the draft", async () => {
    const user = userEvent.setup();
    renderStep(undefined, "vehicle");

    const input = screen.getByText("Пробег (км)").parentElement
      ?.querySelector("input") as HTMLInputElement;
    await user.type(input, "123000");

    expect(input).toHaveValue(123000);
  });

  it("mileage is never required — submit is enabled with it left blank", async () => {
    const user = userEvent.setup();
    renderStep(undefined, "vehicle");

    await user.type(screen.getByText("Оплакване").parentElement
      ?.querySelector("textarea") as HTMLTextAreaElement, "Странен шум");

    expect(screen.getByRole("button", { name: "Създай поръчка" })).not.toBeDisabled();
  });
});

describe("OrderStep — WP-D (Q9/Q10: mileage floor + Owner-only lower-reading bypass)", () => {
  function complaintInput(): HTMLTextAreaElement {
    return screen.getByText("Оплакване").parentElement
      ?.querySelector("textarea") as HTMLTextAreaElement;
  }

  function mileageInput(): HTMLInputElement {
    return screen.getByText("Пробег (км)").parentElement
      ?.querySelector("input") as HTMLInputElement;
  }

  function submitButton(): HTMLElement {
    return screen.getByRole("button", { name: "Създай поръчка" });
  }

  function renderWithFloor(floor: number, isOwner: boolean) {
    mockUseAuth.mockReturnValue({ me: { is_owner: isOwner } });
    mockServiceHistory.mockReturnValue({ current_mileage: floor });
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <Harness assetTypeCode="vehicle" />
      </QueryClientProvider>,
    );
    return within(screen.getByText("Части (по избор)").closest("div") as HTMLElement);
  }

  it("shows the previously recorded mileage as a hint", async () => {
    renderWithFloor(50000, false);
    expect(await screen.findByText("Последно записан пробег: 50000 км")).toBeInTheDocument();
  });

  it("a value at or above the floor needs no confirmation and does not block submit", async () => {
    const user = userEvent.setup();
    renderWithFloor(50000, false);
    await screen.findByText("Последно записан пробег: 50000 км");

    await user.type(complaintInput(), "Странен шум");
    await user.type(mileageInput(), "50000");

    expect(submitButton()).not.toBeDisabled();
    expect(screen.queryByText("Потвърждавам по-малкия пробег")).not.toBeInTheDocument();
  });

  it("a non-Owner gets a flat blocked message, no bypass offered, submit disabled", async () => {
    const user = userEvent.setup();
    renderWithFloor(50000, false);
    await screen.findByText("Последно записан пробег: 50000 км");

    await user.type(complaintInput(), "Странен шум");
    await user.type(mileageInput(), "40000");

    expect(screen.getByText(
      "Пробегът е по-малък от последния записан — само собственикът може да го потвърди.",
    )).toBeInTheDocument();
    expect(screen.queryByText("Потвърждавам по-малкия пробег")).not.toBeInTheDocument();
    expect(submitButton()).toBeDisabled();
  });

  it("an Owner sees the bypass checkbox + comment, both required before submit unblocks", async () => {
    const user = userEvent.setup();
    renderWithFloor(50000, true);
    await screen.findByText("Последно записан пробег: 50000 км");

    await user.type(complaintInput(), "Странен шум");
    await user.type(mileageInput(), "40000");
    expect(submitButton()).toBeDisabled();

    await user.click(screen.getByText("Потвърждавам по-малкия пробег"));
    expect(submitButton()).toBeDisabled(); // checkbox alone isn't enough — comment still required

    const comment = screen.getByPlaceholderText("Коментар (задължителен) — защо пробегът е по-малък…");
    await user.type(comment, "Клиентът смени километража на таблото след ремонт.");

    expect(submitButton()).not.toBeDisabled();
  });

  it("editing the mileage again resets the checkbox and comment, re-blocking submit", async () => {
    const user = userEvent.setup();
    renderWithFloor(50000, true);
    await screen.findByText("Последно записан пробег: 50000 км");

    await user.type(complaintInput(), "Странен шум");
    await user.type(mileageInput(), "40000");
    await user.click(screen.getByText("Потвърждавам по-малкия пробег"));
    await user.type(
      screen.getByPlaceholderText("Коментар (задължителен) — защо пробегът е по-малък…"),
      "Коментар.",
    );
    expect(submitButton()).not.toBeDisabled();

    // Still below the floor (45000 < 50000) — a different value, so the
    // stale confirmation must not silently carry over: the checkbox is
    // back to unchecked and the comment field is gone, not pre-filled.
    const input = mileageInput();
    await user.clear(input);
    await user.type(input, "45000");

    expect(screen.getByRole("checkbox")).not.toBeChecked();
    expect(screen.queryByPlaceholderText(
      "Коментар (задължителен) — защо пробегът е по-малък…",
    )).not.toBeInTheDocument();
    expect(submitButton()).toBeDisabled();
  });
});

describe("OrderStep — Wave 5 Issue 12 (order delivery method/address)", () => {
  it("defaults to pickup, with no delivery-address field shown", () => {
    renderStep();
    expect(screen.getByRole("button", { name: "Взимане от сервиза" }))
      .toHaveAttribute("aria-pressed", "true");
    expect(screen.queryByLabelText("Адрес за доставка")).not.toBeInTheDocument();
  });

  it("shows the delivery-address field only once courier is chosen", async () => {
    const user = userEvent.setup();
    renderStep();

    await user.click(screen.getByRole("button", { name: "Куриер" }));

    expect(screen.getByLabelText("Адрес за доставка")).toBeInTheDocument();
  });

  it("prefills the delivery address from the customer's default once courier is chosen", async () => {
    const user = userEvent.setup();
    renderStep(undefined, "phone", "ул. Тестова 5");

    await user.click(screen.getByRole("button", { name: "Куриер" }));

    expect(screen.getByLabelText("Адрес за доставка")).toHaveValue("ул. Тестова 5");
  });

  it("never overwrites an address the user already typed", async () => {
    const user = userEvent.setup();
    renderStep(undefined, "phone", "адрес по подразбиране");

    await user.click(screen.getByRole("button", { name: "Куриер" }));
    const input = screen.getByLabelText("Адрес за доставка");
    await user.clear(input);
    await user.type(input, "ръчно въведен адрес");
    await user.click(screen.getByRole("button", { name: "Взимане от сервиза" }));
    await user.click(screen.getByRole("button", { name: "Куриер" }));

    expect(screen.getByLabelText("Адрес за доставка")).toHaveValue("ръчно въведен адрес");
  });
});

describe("OrderStep — WP-E #10/#12 (camera/folder capture buttons, client thumbnails)", () => {
  // jsdom has no real createObjectURL implementation.
  beforeEach(() => {
    vi.stubGlobal("URL", {
      ...URL, createObjectURL: vi.fn(() => "blob:mock"), revokeObjectURL: vi.fn(),
    });
  });

  function galleryInput(): HTMLInputElement {
    // Camera input first, gallery/"choose from device" input second — see
    // PhotoCaptureButtons' render order. There's exactly one OrderStep per
    // test, so a document-wide query is unambiguous.
    return document.querySelectorAll('input[type="file"]')[1] as HTMLInputElement;
  }

  it("shows explicit camera and gallery buttons instead of a generic drop-zone", () => {
    renderStep();
    expect(screen.getByRole("button", { name: /Снимай/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /От устройството/ })).toBeInTheDocument();
  });

  it("adding a photo via the gallery input shows a client-side thumbnail", async () => {
    const user = userEvent.setup();
    renderStep();
    const file = new File(["x"], "photo.jpg", { type: "image/jpeg" });

    await user.upload(galleryInput(), file);

    expect(await screen.findByAltText("photo.jpg")).toBeInTheDocument();
  });

  it("removing an added photo removes its thumbnail", async () => {
    const user = userEvent.setup();
    renderStep();
    const file = new File(["x"], "photo.jpg", { type: "image/jpeg" });
    await user.upload(galleryInput(), file);
    const thumb = await screen.findByAltText("photo.jpg");

    await user.click(within(thumb.closest("li") as HTMLElement).getByLabelText("Затвори"));

    expect(screen.queryByAltText("photo.jpg")).not.toBeInTheDocument();
  });
});

describe("OrderStep — Issue 29 (parts addable at intake)", () => {
  it("shows the parts section with an empty-state message by default", () => {
    const parts = renderStep();
    expect(parts.getByText("Няма добавени части.")).toBeInTheDocument();
  });

  it("adding a part line shows it in the list with name and price", async () => {
    const user = userEvent.setup();
    const parts = renderStep();

    await user.type(parts.getByPlaceholderText("Име на частта…"), "Дисплей");
    await user.type(parts.getByPlaceholderText("€"), "85");
    await user.click(parts.getByRole("button", { name: "Добави" }));

    expect(parts.getByText("Дисплей · 85.00 €")).toBeInTheDocument();
    expect(parts.queryByText("Няма добавени части.")).not.toBeInTheDocument();
  });

  it("clears the name/price inputs after adding", async () => {
    const user = userEvent.setup();
    const parts = renderStep();

    await user.type(parts.getByPlaceholderText("Име на частта…"), "Дисплей");
    await user.type(parts.getByPlaceholderText("€"), "85");
    await user.click(parts.getByRole("button", { name: "Добави" }));

    expect(parts.getByPlaceholderText("Име на частта…")).toHaveValue("");
    expect(parts.getByPlaceholderText("€")).toHaveValue(null);
  });

  it("added part lines render pre-seeded, and can be removed", async () => {
    const user = userEvent.setup();
    const parts = renderStep({ ...DEFAULT_VALUE, partLines: [{ name: "Батерия", unitPrice: 32 }] });

    expect(parts.getByText("Батерия · 32.00 €")).toBeInTheDocument();
    await user.click(parts.getByLabelText("Затвори"));
    expect(parts.queryByText("Батерия · 32.00 €")).not.toBeInTheDocument();
    expect(parts.getByText("Няма добавени части.")).toBeInTheDocument();
  });

  it("does not add an empty-name part line", async () => {
    const user = userEvent.setup();
    const parts = renderStep();

    await user.type(parts.getByPlaceholderText("€"), "10");
    await user.click(parts.getByRole("button", { name: "Добави" }));

    expect(parts.getByText("Няма добавени части.")).toBeInTheDocument();
  });

  it("defaults an omitted price to 0", async () => {
    const user = userEvent.setup();
    const parts = renderStep();

    await user.type(parts.getByPlaceholderText("Име на частта…"), "Винт");
    await user.click(parts.getByRole("button", { name: "Добави" }));

    expect(parts.getByText("Винт · 0.00 €")).toBeInTheDocument();
  });
});
