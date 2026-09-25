import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../lib/api";
import { CustomerCompanyDetailsSection } from "./CustomerCompanyDetailsSection";
import type { CustomerDetail } from "./types";

vi.mock("../lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../lib/api")>();
  return { ...actual, api: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), put: vi.fn(), delete: vi.fn() } };
});

beforeEach(() => {
  vi.mocked(api.patch).mockReset();
});

const individualCustomer: CustomerDetail = {
  id: "c1", name: "Иван Петров", phone: "0888123456", phone2: null, email: null,
  is_company: false, vat_registered: null, company_requisites: null,
  delivery_address: null, archived: false, anonymized: false,
};

const companyCustomerUnknown: CustomerDetail = {
  id: "c2", name: "Пример ЕООД", phone: "029001122", phone2: null, email: null,
  is_company: true, vat_registered: null,
  company_requisites: { country: "BG", address: "гр. София", eik: "130489869", vat_number: null },
  delivery_address: null, archived: false, anonymized: false,
};

const companyCustomerRegistered: CustomerDetail = {
  id: "c3", name: "ДДС ЕООД", phone: "029001133", phone2: null, email: null,
  is_company: true, vat_registered: true,
  company_requisites: {
    country: "BG", address: "гр. Варна", eik: "130489869", vat_number: "BG130489869",
  },
  delivery_address: null, archived: false, anonymized: false,
};

function renderSection(customer: CustomerDetail) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <CustomerCompanyDetailsSection customerId={customer.id} customer={customer} />
    </QueryClientProvider>,
  );
}

describe("CustomerCompanyDetailsSection", () => {
  it("shows a neutral message for an individual customer", () => {
    renderSection(individualCustomer);
    expect(screen.getByText("Клиентът е физическо лице.")).toBeInTheDocument();
  });

  it("shows the stored requisites read-only for a company customer", () => {
    renderSection(companyCustomerUnknown);
    expect(screen.getByText("гр. София")).toBeInTheDocument();
    expect(screen.getByText("130489869")).toBeInTheDocument();
  });

  it("shows the unknown VAT-status hint and no VAT number for an unconfirmed company", () => {
    renderSection(companyCustomerUnknown);
    expect(screen.getByText("Не е проверено")).toBeInTheDocument();
    expect(screen.getByText(/не може да бъде издадена фактура/)).toBeInTheDocument();
    expect(screen.queryByText("ДДС номер")).not.toBeInTheDocument();
  });

  it("shows the VAT number read-only for a VAT-registered company", () => {
    renderSection(companyCustomerRegistered);
    expect(screen.getByText("Да")).toBeInTheDocument();
    expect(screen.getByText("BG130489869")).toBeInTheDocument();
  });

  it("prefills the edit form with the existing company requisites", async () => {
    const user = userEvent.setup();
    renderSection(companyCustomerUnknown);

    await user.click(screen.getByRole("button", { name: "Промени" }));

    expect(screen.getByLabelText("Адрес")).toHaveValue("гр. София");
    expect(screen.getByLabelText("ЕИК / БУЛСТАТ")).toHaveValue("130489869");
    expect(screen.getByRole("button", { name: "Фирма" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.queryByRole("button", { name: "Не е проверено" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Да" })).toHaveAttribute("aria-pressed", "false");
    expect(screen.getByRole("button", { name: "Не" })).toHaveAttribute("aria-pressed", "false");
  });

  it("prefills the VAT number when editing an already-registered company", async () => {
    const user = userEvent.setup();
    renderSection(companyCustomerRegistered);

    await user.click(screen.getByRole("button", { name: "Промени" }));

    expect(screen.getByRole("button", { name: "Да" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByLabelText("ДДС номер")).toHaveValue("BG130489869");
  });

  it("submits edited requisites via PATCH with the exact expected payload", async () => {
    const user = userEvent.setup();
    vi.mocked(api.patch).mockResolvedValue({});
    renderSection(companyCustomerUnknown);

    await user.click(screen.getByRole("button", { name: "Промени" }));
    await user.clear(screen.getByLabelText("ЕИК / БУЛСТАТ"));
    await user.type(screen.getByLabelText("ЕИК / БУЛСТАТ"), "175074752");
    await user.click(screen.getByRole("button", { name: "Запази" }));

    expect(api.patch).toHaveBeenCalledWith("/customers/c2", {
      is_company: true,
      vat_registered: null,
      company_requisites: { country: "BG", address: "гр. София", eik: "175074752", vat_number: null },
    });
  });

  it("choosing VAT status 'Не' clears any draft VAT number from the save payload", async () => {
    const user = userEvent.setup();
    vi.mocked(api.patch).mockResolvedValue({});
    renderSection(companyCustomerRegistered);

    await user.click(screen.getByRole("button", { name: "Промени" }));
    await user.click(screen.getByRole("button", { name: "Не" }));
    expect(screen.queryByLabelText("ДДС номер")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Запази" }));

    expect(api.patch).toHaveBeenCalledWith("/customers/c3", {
      is_company: true,
      vat_registered: false,
      company_requisites: { country: "BG", address: "гр. Варна", eik: "130489869", vat_number: null },
    });
  });

  it("choosing VAT status 'Да' saves the (Wave 5 auto-prefilled) VAT number", async () => {
    const user = userEvent.setup();
    vi.mocked(api.patch).mockResolvedValue({});
    renderSection(companyCustomerUnknown);

    await user.click(screen.getByRole("button", { name: "Промени" }));
    // EIK "130489869" is already on file, so choosing "Да" alone already
    // fills the VAT number (Wave 5) — no manual typing needed.
    await user.click(screen.getByRole("button", { name: "Да" }));
    await user.click(screen.getByRole("button", { name: "Запази" }));

    expect(api.patch).toHaveBeenCalledWith("/customers/c2", {
      is_company: true,
      vat_registered: true,
      company_requisites: { country: "BG", address: "гр. София", eik: "130489869", vat_number: "BG130489869" },
    });
  });

  it("switching to Физическо лице during edit does not erase stored requisites on save", async () => {
    const user = userEvent.setup();
    vi.mocked(api.patch).mockResolvedValue({});
    renderSection(companyCustomerRegistered);

    await user.click(screen.getByRole("button", { name: "Промени" }));
    await user.click(screen.getByRole("button", { name: "Физическо лице" }));
    expect(screen.queryByLabelText("Адрес")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Запази" }));

    expect(api.patch).toHaveBeenCalledWith("/customers/c3", {
      is_company: false,
      vat_registered: true,
      company_requisites: { country: "BG", address: "гр. Варна", eik: "130489869", vat_number: "BG130489869" },
    });
  });

  it("switching to Фирма for an individual customer reveals empty company fields with unknown VAT status", async () => {
    const user = userEvent.setup();
    renderSection(individualCustomer);

    await user.click(screen.getByRole("button", { name: "Промени" }));
    await user.click(screen.getByRole("button", { name: "Фирма" }));

    expect(screen.getByLabelText("Адрес")).toHaveValue("");
    expect(screen.getByLabelText("ЕИК / БУЛСТАТ")).toHaveValue("");
    expect(screen.queryByRole("button", { name: "Не е проверено" })).not.toBeInTheDocument();
    expect(screen.queryByLabelText("ДДС номер")).not.toBeInTheDocument();
  });
});

describe("CustomerCompanyDetailsSection — Wave 5 Issue 11/12 (country + BG VAT prefill)", () => {
  it("defaults a brand-new company's country to България", async () => {
    const user = userEvent.setup();
    renderSection(individualCustomer);

    await user.click(screen.getByRole("button", { name: "Промени" }));
    await user.click(screen.getByRole("button", { name: "Фирма" }));

    expect(screen.getByLabelText("Държава")).toHaveValue("BG");
  });

  it("prefills the VAT number from a valid BG EIK once VAT registration is confirmed", async () => {
    const user = userEvent.setup();
    renderSection(companyCustomerUnknown);

    await user.click(screen.getByRole("button", { name: "Промени" }));
    await user.click(screen.getByRole("button", { name: "Да" }));

    expect(screen.getByLabelText("ДДС номер")).toHaveValue("BG130489869");
  });

  it("does not prefill a VAT number for a non-BG country", async () => {
    const user = userEvent.setup();
    renderSection(companyCustomerUnknown);

    await user.click(screen.getByRole("button", { name: "Промени" }));
    await user.selectOptions(screen.getByLabelText("Държава"), "DE");
    await user.click(screen.getByRole("button", { name: "Да" }));

    expect(screen.getByLabelText("ДДС номер")).toHaveValue("");
  });

  it("saves the selected country in the requisites payload", async () => {
    const user = userEvent.setup();
    vi.mocked(api.patch).mockResolvedValue({});
    renderSection(companyCustomerUnknown);

    await user.click(screen.getByRole("button", { name: "Промени" }));
    await user.selectOptions(screen.getByLabelText("Държава"), "DE");
    await user.click(screen.getByRole("button", { name: "Запази" }));

    expect(api.patch).toHaveBeenCalledWith("/customers/c2", expect.objectContaining({
      company_requisites: expect.objectContaining({ country: "DE" }),
    }));
  });
});
