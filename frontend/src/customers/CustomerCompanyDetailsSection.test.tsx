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
  is_company: false, company_requisites: null, archived: false, anonymized: false,
};

const companyCustomer: CustomerDetail = {
  id: "c2", name: "Пример ЕООД", phone: "029001122", phone2: null, email: null,
  is_company: true, company_requisites: { address: "гр. София", eik: "130489869" },
  archived: false, anonymized: false,
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
    renderSection(companyCustomer);
    expect(screen.getByText("гр. София")).toBeInTheDocument();
    expect(screen.getByText("130489869")).toBeInTheDocument();
  });

  it("prefills the edit form with the existing company requisites", async () => {
    const user = userEvent.setup();
    renderSection(companyCustomer);

    await user.click(screen.getByRole("button", { name: "Промени" }));

    expect(screen.getByLabelText("Адрес")).toHaveValue("гр. София");
    expect(screen.getByLabelText("ЕИК / БУЛСТАТ")).toHaveValue("130489869");
    expect(screen.getByRole("button", { name: "Фирма" })).toHaveAttribute("aria-pressed", "true");
  });

  it("submits edited requisites via PATCH with the exact expected payload", async () => {
    const user = userEvent.setup();
    vi.mocked(api.patch).mockResolvedValue({});
    renderSection(companyCustomer);

    await user.click(screen.getByRole("button", { name: "Промени" }));
    await user.clear(screen.getByLabelText("ЕИК / БУЛСТАТ"));
    await user.type(screen.getByLabelText("ЕИК / БУЛСТАТ"), "175074752");
    await user.click(screen.getByRole("button", { name: "Запази" }));

    expect(api.patch).toHaveBeenCalledWith("/customers/c2", {
      is_company: true,
      company_requisites: { address: "гр. София", eik: "175074752" },
    });
  });

  it("switching to Физическо лице during edit does not erase stored requisites on save", async () => {
    const user = userEvent.setup();
    vi.mocked(api.patch).mockResolvedValue({});
    renderSection(companyCustomer);

    await user.click(screen.getByRole("button", { name: "Промени" }));
    await user.click(screen.getByRole("button", { name: "Физическо лице" }));
    expect(screen.queryByLabelText("Адрес")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Запази" }));

    expect(api.patch).toHaveBeenCalledWith("/customers/c2", {
      is_company: false,
      company_requisites: { address: "гр. София", eik: "130489869" },
    });
  });

  it("switching to Фирма for an individual customer reveals empty company fields", async () => {
    const user = userEvent.setup();
    renderSection(individualCustomer);

    await user.click(screen.getByRole("button", { name: "Промени" }));
    await user.click(screen.getByRole("button", { name: "Фирма" }));

    expect(screen.getByLabelText("Адрес")).toHaveValue("");
    expect(screen.getByLabelText("ЕИК / БУЛСТАТ")).toHaveValue("");
  });
});
