import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../lib/api";
import { CustomerDeliveryAddressSection } from "./CustomerDeliveryAddressSection";
import type { CustomerDetail } from "./types";

vi.mock("../lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../lib/api")>();
  return { ...actual, api: { ...actual.api, patch: vi.fn() } };
});

beforeEach(() => {
  vi.mocked(api.patch).mockReset();
});

const individualNoOverride: CustomerDetail = {
  id: "c1", name: "Иван Петров", phone: "0888123456", phone2: null, email: null,
  is_company: false, vat_registered: null, company_requisites: null,
  address: "ул. Главна 1", delivery_address: null, archived: false, anonymized: false,
};

const individualWithOverride: CustomerDetail = {
  ...individualNoOverride,
  delivery_address: { address: "ул. Складова 9" },
};

const companyNoOverride: CustomerDetail = {
  id: "c2", name: "Фирма ЕООД", phone: "029001122", phone2: null, email: null,
  is_company: true, vat_registered: null,
  company_requisites: { country: "BG", address: "гр. Пловдив", eik: "130489869", vat_number: null },
  address: null, delivery_address: null, archived: false, anonymized: false,
};

function renderSection(customer: CustomerDetail) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <CustomerDeliveryAddressSection customerId={customer.id} customer={customer} />
    </QueryClientProvider>,
  );
}

describe("CustomerDeliveryAddressSection — read-time fallback (order-workflow-revamp WP-B, Q20b)", () => {
  it("shows the explicit delivery address when one is on file", () => {
    renderSection(individualWithOverride);
    expect(screen.getByText("ул. Складова 9")).toBeInTheDocument();
  });

  it("falls back to the individual's own main address when none is on file", () => {
    renderSection(individualNoOverride);
    expect(screen.getByText("ул. Главна 1", { exact: false })).toBeInTheDocument();
  });

  it("falls back to the company's main address when none is on file", () => {
    renderSection(companyNoOverride);
    expect(screen.getByText("гр. Пловдив", { exact: false })).toBeInTheDocument();
  });

  it("shows a neutral message when neither a delivery nor a main address exists", () => {
    renderSection({ ...individualNoOverride, address: null });
    expect(screen.getByText("Няма зададен адрес за доставка.")).toBeInTheDocument();
  });
});

describe("CustomerDeliveryAddressSection — edit checkbox semantics", () => {
  it("starts unchecked, with no field, for a customer with no override", async () => {
    const user = userEvent.setup();
    renderSection(individualNoOverride);
    await user.click(screen.getByRole("button", { name: "Промени" }));

    expect(screen.getByRole("checkbox", { name: "Адресът за доставка е различен" })).not.toBeChecked();
    expect(screen.queryByLabelText("Адрес за доставка")).not.toBeInTheDocument();
  });

  it("starts checked, prefilled, for a customer with an override", async () => {
    const user = userEvent.setup();
    renderSection(individualWithOverride);
    await user.click(screen.getByRole("button", { name: "Промени" }));

    expect(screen.getByRole("checkbox", { name: "Адресът за доставка е различен" })).toBeChecked();
    expect(screen.getByLabelText("Адрес за доставка")).toHaveValue("ул. Складова 9");
  });

  it("saves null (not a copy of the main address) when unchecked", async () => {
    const user = userEvent.setup();
    vi.mocked(api.patch).mockResolvedValue({});
    renderSection(individualWithOverride);

    await user.click(screen.getByRole("button", { name: "Промени" }));
    await user.click(screen.getByRole("checkbox", { name: "Адресът за доставка е различен" }));
    await user.click(screen.getByRole("button", { name: "Запази" }));

    expect(api.patch).toHaveBeenCalledWith("/customers/c1", { delivery_address: null });
  });

  it("saves the typed override once checked", async () => {
    const user = userEvent.setup();
    vi.mocked(api.patch).mockResolvedValue({});
    renderSection(individualNoOverride);

    await user.click(screen.getByRole("button", { name: "Промени" }));
    await user.click(screen.getByRole("checkbox", { name: "Адресът за доставка е различен" }));
    await user.type(screen.getByLabelText("Адрес за доставка"), "ул. Нова 2");
    await user.click(screen.getByRole("button", { name: "Запази" }));

    expect(api.patch).toHaveBeenCalledWith("/customers/c1", {
      delivery_address: { address: "ул. Нова 2" },
    });
  });
});
