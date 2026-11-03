import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../lib/api";
import { CustomerStep } from "./CustomerStep";

vi.mock("../lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../lib/api")>();
  return { ...actual, api: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), put: vi.fn(), delete: vi.fn() } };
});

beforeEach(() => {
  vi.mocked(api.get).mockReset();
  vi.mocked(api.post).mockReset();
});

function renderStep() {
  const onResolved = vi.fn();
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <CustomerStep resolved={null} onResolved={onResolved} onChangeRequested={vi.fn()} />
    </QueryClientProvider>,
  );
  return { onResolved };
}

async function enterCreateMode(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByRole("button", { name: "+ Нов клиент" }));
}

describe("CustomerStep create flow", () => {
  it("creates an individual customer unchanged (no company fields sent)", async () => {
    const user = userEvent.setup();
    vi.mocked(api.post).mockResolvedValue({
      id: "c1", name: "Иван Петров", phone: "0888123456",
    });
    const { onResolved } = renderStep();

    await enterCreateMode(user);
    await user.type(screen.getByPlaceholderText("Име"), "Иван Петров");
    await user.type(screen.getByPlaceholderText("Телефон"), "0888123456");
    await user.click(screen.getByRole("button", { name: "Продължи" }));

    expect(api.post).toHaveBeenCalledWith("/customers", {
      name: "Иван Петров", phone: "0888123456", email: null,
      is_company: false, vat_registered: null, company_requisites: null,
      address: null, delivery_address: null,
    });
    expect(onResolved).toHaveBeenCalledWith(
      expect.objectContaining({ id: "c1", name: "Иван Петров", phone: "0888123456" }),
    );
  });

  it("hides company fields for an individual customer by default", async () => {
    const user = userEvent.setup();
    renderStep();
    await enterCreateMode(user);

    expect(screen.queryByLabelText("Адрес")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("ЕИК / БУЛСТАТ")).not.toBeInTheDocument();
  });

  it("switching the type toggle to Фирма reveals company fields", async () => {
    const user = userEvent.setup();
    renderStep();
    await enterCreateMode(user);

    await user.click(screen.getByRole("button", { name: "Фирма" }));

    expect(screen.getByLabelText("Адрес")).toBeInTheDocument();
    expect(screen.getByLabelText("ЕИК / БУЛСТАТ")).toBeInTheDocument();
  });

  it("switching the type toggle to Фирма relabels the name field as company name", async () => {
    const user = userEvent.setup();
    renderStep();
    await enterCreateMode(user);

    expect(screen.getByPlaceholderText("Име")).toBeInTheDocument();
    expect(screen.queryByPlaceholderText("Име на фирма")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Фирма" }));

    expect(screen.getByPlaceholderText("Име на фирма")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Име на фирма")).toBeRequired();
    expect(screen.queryByPlaceholderText("Име")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Физическо лице" }));
    expect(screen.getByPlaceholderText("Име")).toBeInTheDocument();
  });

  it("places the Individual/Company selector above the name field", async () => {
    const user = userEvent.setup();
    renderStep();
    await enterCreateMode(user);

    const toggle = screen.getByRole("group", { name: "Тип клиент" });
    const nameField = screen.getByPlaceholderText("Име");

    expect(toggle.compareDocumentPosition(nameField) & Node.DOCUMENT_POSITION_FOLLOWING)
      .toBeTruthy();
  });

  it("switching back to Физическо лице hides the company fields again", async () => {
    const user = userEvent.setup();
    renderStep();
    await enterCreateMode(user);

    await user.click(screen.getByRole("button", { name: "Фирма" }));
    expect(screen.getByLabelText("Адрес")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Физическо лице" }));
    expect(screen.queryByLabelText("Адрес")).not.toBeInTheDocument();
  });

  it("creates a company customer with the approved requisites", async () => {
    const user = userEvent.setup();
    vi.mocked(api.post).mockResolvedValue({
      id: "c2", name: "Пример ЕООД", phone: "029001122",
    });
    renderStep();

    await enterCreateMode(user);
    await user.type(screen.getByPlaceholderText("Име"), "Пример ЕООД");
    await user.type(screen.getByPlaceholderText("Телефон"), "029001122");
    await user.click(screen.getByRole("button", { name: "Фирма" }));
    await user.type(screen.getByLabelText("Адрес"), "гр. София");
    await user.type(screen.getByLabelText("ЕИК / БУЛСТАТ"), "130489869");
    await user.click(screen.getByRole("button", { name: "Продължи" }));

    expect(api.post).toHaveBeenCalledWith("/customers", {
      name: "Пример ЕООД", phone: "029001122", email: null,
      is_company: true, vat_registered: null,
      company_requisites: { country: "BG", address: "гр. София", eik: "130489869", vat_number: null },
      address: null, delivery_address: null,
    });
  });

  it("creates a VAT-registered company customer with the VAT number", async () => {
    const user = userEvent.setup();
    vi.mocked(api.post).mockResolvedValue({
      id: "c3", name: "ДДС ЕООД", phone: "029001133",
    });
    renderStep();

    await enterCreateMode(user);
    await user.type(screen.getByPlaceholderText("Име"), "ДДС ЕООД");
    await user.type(screen.getByPlaceholderText("Телефон"), "029001133");
    await user.click(screen.getByRole("button", { name: "Фирма" }));
    await user.type(screen.getByLabelText("Адрес"), "гр. Варна");
    await user.type(screen.getByLabelText("ЕИК / БУЛСТАТ"), "130489869");
    // Wave 5: a valid BG EIK is already on file, so choosing "Да" alone
    // already fills the VAT number — no manual typing needed.
    await user.click(screen.getByRole("button", { name: "Да" }));
    await user.click(screen.getByRole("button", { name: "Продължи" }));

    expect(api.post).toHaveBeenCalledWith("/customers", {
      name: "ДДС ЕООД", phone: "029001133", email: null,
      is_company: true, vat_registered: true,
      company_requisites: { country: "BG", address: "гр. Варна", eik: "130489869", vat_number: "BG130489869" },
      address: null, delivery_address: null,
    });
  });

  it("defaults new company customers to unknown VAT status with an explanatory hint", async () => {
    const user = userEvent.setup();
    renderStep();
    await enterCreateMode(user);

    await user.click(screen.getByRole("button", { name: "Фирма" }));

    expect(screen.queryByRole("button", { name: "Не е проверено" })).not.toBeInTheDocument();
    expect(screen.getByText(/не може да бъде издадена фактура/)).toBeInTheDocument();
    expect(screen.queryByLabelText("ДДС номер")).not.toBeInTheDocument();
  });

  it("the VAT-number input only appears once 'Да' is selected", async () => {
    const user = userEvent.setup();
    renderStep();
    await enterCreateMode(user);
    await user.click(screen.getByRole("button", { name: "Фирма" }));

    expect(screen.queryByLabelText("ДДС номер")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Да" }));
    expect(screen.getByLabelText("ДДС номер")).toBeInTheDocument();
  });
});

describe("CustomerStep — delivery address (order-workflow-revamp WP-B: checkbox-gated, Q20b)", () => {
  it("sends the entered delivery address once the checkbox is ticked", async () => {
    const user = userEvent.setup();
    vi.mocked(api.post).mockResolvedValue({
      id: "c4", name: "Мария", phone: "0888555444",
    });
    renderStep();

    await enterCreateMode(user);
    await user.type(screen.getByPlaceholderText("Име"), "Мария");
    await user.type(screen.getByPlaceholderText("Телефон"), "0888555444");
    await user.click(screen.getByRole("checkbox", { name: "Адресът за доставка е различен" }));
    await user.type(screen.getByPlaceholderText("Адрес за доставка"), "ул. Тестова 5");
    await user.click(screen.getByRole("button", { name: "Продължи" }));

    expect(api.post).toHaveBeenCalledWith("/customers", expect.objectContaining({
      delivery_address: { address: "ул. Тестова 5" },
    }));
  });

  it("omits the delivery address when the checkbox stays unticked", async () => {
    const user = userEvent.setup();
    vi.mocked(api.post).mockResolvedValue({
      id: "c5", name: "Петър", phone: "0888555111",
    });
    renderStep();

    await enterCreateMode(user);
    await user.type(screen.getByPlaceholderText("Име"), "Петър");
    await user.type(screen.getByPlaceholderText("Телефон"), "0888555111");
    await user.click(screen.getByRole("button", { name: "Продължи" }));

    expect(api.post).toHaveBeenCalledWith("/customers", expect.objectContaining({
      delivery_address: null,
    }));
  });

  it("hides the delivery-address field until the checkbox is ticked", async () => {
    const user = userEvent.setup();
    renderStep();
    await enterCreateMode(user);

    expect(screen.queryByPlaceholderText("Адрес за доставка")).not.toBeInTheDocument();
    await user.click(screen.getByRole("checkbox", { name: "Адресът за доставка е различен" }));
    expect(screen.getByPlaceholderText("Адрес за доставка")).toBeInTheDocument();
  });
});

describe("CustomerStep — duplicate phone resolves to the existing customer (order-workflow-revamp WP-B, Q7)", () => {
  it("on-blur duplicate match offers a pick-existing action that resolves without creating", async () => {
    const user = userEvent.setup();
    vi.mocked(api.get).mockResolvedValue({
      duplicate: { id: "existing-1", name: "Иван Петров" },
    });
    const { onResolved } = renderStep();

    await enterCreateMode(user);
    await user.type(screen.getByPlaceholderText("Име"), "Иван Петров (дубликат)");
    await user.type(screen.getByPlaceholderText("Телефон"), "0888123456");
    await user.tab(); // blur the phone field

    const pick = await screen.findByRole("button", { name: "Избери съществуващия клиент" });
    await user.click(pick);

    expect(onResolved).toHaveBeenCalledWith({
      id: "existing-1", name: "Иван Петров", phone: "0888123456",
    });
    expect(api.post).not.toHaveBeenCalled();
  });

  it("disables submit while a duplicate match is active", async () => {
    const user = userEvent.setup();
    vi.mocked(api.get).mockResolvedValue({
      duplicate: { id: "existing-1", name: "Иван Петров" },
    });
    renderStep();

    await enterCreateMode(user);
    await user.type(screen.getByPlaceholderText("Име"), "Иван Петров (дубликат)");
    await user.type(screen.getByPlaceholderText("Телефон"), "0888123456");
    await user.tab();

    await screen.findByRole("button", { name: "Избери съществуващия клиент" });
    expect(screen.getByRole("button", { name: "Продължи" })).toBeDisabled();
  });
});

describe("CustomerStep — Wave 5 Issue 11 (BG VAT-number prefill at create)", () => {
  it("prefills the VAT number once a valid BG EIK is entered and VAT is confirmed registered", async () => {
    const user = userEvent.setup();
    vi.mocked(api.post).mockResolvedValue({
      id: "c6", name: "ДДС ЕООД", phone: "029001199",
    });
    renderStep();

    await enterCreateMode(user);
    await user.type(screen.getByPlaceholderText("Име"), "ДДС ЕООД");
    await user.type(screen.getByPlaceholderText("Телефон"), "029001199");
    await user.click(screen.getByRole("button", { name: "Фирма" }));
    await user.type(screen.getByLabelText("ЕИК / БУЛСТАТ"), "130489869");
    await user.click(screen.getByRole("button", { name: "Да" }));

    expect(screen.getByLabelText("ДДС номер")).toHaveValue("BG130489869");
  });
});
