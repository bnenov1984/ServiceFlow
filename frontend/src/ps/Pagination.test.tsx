import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { PAGE_SIZE, PaginationFooter, paginate } from "./Pagination";

describe("paginate", () => {
  it("slices items into pages of PAGE_SIZE", () => {
    const items = Array.from({ length: 20 }, (_, i) => i);
    expect(paginate(items, 0)).toEqual(items.slice(0, PAGE_SIZE));
    expect(paginate(items, 1)).toEqual(items.slice(PAGE_SIZE, PAGE_SIZE * 2));
    expect(paginate(items, 2)).toEqual(items.slice(PAGE_SIZE * 2));
  });

  it("returns an empty slice for a page past the end", () => {
    const items = [1, 2, 3];
    expect(paginate(items, 5)).toEqual([]);
  });
});

describe("PaginationFooter", () => {
  it("renders nothing when total is 0", () => {
    const { container } = render(
      <PaginationFooter page={0} total={0} onPageChange={vi.fn()} />,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("shows the correct 1-indexed range and disables prev on the first page", () => {
    render(<PaginationFooter page={0} total={20} onPageChange={vi.fn()} />);
    expect(screen.getByText(`Показване на 1–${PAGE_SIZE} от 20`)).toBeInTheDocument();
    expect(screen.getByLabelText("Предишна страница")).toBeDisabled();
    expect(screen.getByLabelText("Следваща страница")).not.toBeDisabled();
  });

  it("disables next on the last page and clamps the shown \"to\" value to the total", () => {
    render(<PaginationFooter page={2} total={20} onPageChange={vi.fn()} />);
    expect(screen.getByText("Показване на 17–20 от 20")).toBeInTheDocument();
    expect(screen.getByLabelText("Следваща страница")).toBeDisabled();
  });

  it("calls onPageChange with the adjacent page on prev/next click", async () => {
    const onPageChange = vi.fn();
    const user = userEvent.setup();
    render(<PaginationFooter page={1} total={20} onPageChange={onPageChange} />);

    await user.click(screen.getByLabelText("Следваща страница"));
    expect(onPageChange).toHaveBeenCalledWith(2);

    await user.click(screen.getByLabelText("Предишна страница"));
    expect(onPageChange).toHaveBeenCalledWith(0);
  });
});
