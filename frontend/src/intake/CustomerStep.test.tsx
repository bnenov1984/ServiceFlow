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
      id: "c1", name: "Иван Петров", phone: "0888123456", archived: false, duplicate_ids: [],
    });
    const { onResolved } = renderStep();

    await enterCreateMode(user);
    await user.type(screen.getByPlaceholderText("Име"), "Иван Петров");
    await user.type(screen.getByPlaceholderText("Телефон"), "0888123456");
    await user.click(screen.getByRole("button", { name: "Продължи" }));

    expect(api.post).toHaveBeenCalledWith("/customers", {
      name: "Иван Петров", phone: "0888123456", email: null,
      is_company: false, vat_registered: null, company_requisites: null,
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
      id: "c2", name: "Пример ЕООД", phone: "029001122", archived: false, duplicate_ids: [],
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
      company_requisites: { address: "гр. София", eik: "130489869", vat_number: null },
    });
  });

  it("creates a VAT-registered company customer with the VAT number", async () => {
    const user = userEvent.setup();
    vi.mocked(api.post).mockResolvedValue({
      id: "c3", name: "ДДС ЕООД", phone: "029001133", archived: false, duplicate_ids: [],
    });
    renderStep();

    await enterCreateMode(user);
    await user.type(screen.getByPlaceholderText("Име"), "ДДС ЕООД");
    await user.type(screen.getByPlaceholderText("Телефон"), "029001133");
    await user.click(screen.getByRole("button", { name: "Фирма" }));
    await user.type(screen.getByLabelText("Адрес"), "гр. Варна");
    await user.type(screen.getByLabelText("ЕИК / БУЛСТАТ"), "130489869");
    await user.click(screen.getByRole("button", { name: "Да" }));
    await user.type(screen.getByLabelText("ДДС номер"), "BG130489869");
    await user.click(screen.getByRole("button", { name: "Продължи" }));

    expect(api.post).toHaveBeenCalledWith("/customers", {
      name: "ДДС ЕООД", phone: "029001133", email: null,
      is_company: true, vat_registered: true,
      company_requisites: { address: "гр. Варна", eik: "130489869", vat_number: "BG130489869" },
    });
  });

  it("defaults new company customers to unknown VAT status with an explanatory hint", async () => {
    const user = userEvent.setup();
    renderStep();
    await enterCreateMode(user);

    await user.click(screen.getByRole("button", { name: "Фирма" }));

    expect(screen.getByRole("button", { name: "Не е проверено" })).toHaveAttribute("aria-pressed", "true");
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
