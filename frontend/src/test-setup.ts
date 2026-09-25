import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

// With `globals: false` RTL's automatic cleanup can't self-register.
afterEach(cleanup);

// jsdom doesn't implement the native <dialog> element's modal methods
// (components/Dialog.tsx relies on them) — needed once a Dialog-based
// component (e.g. CompletionDialog) is rendered under test.
if (!HTMLDialogElement.prototype.showModal) {
  HTMLDialogElement.prototype.showModal = function (this: HTMLDialogElement) {
    this.setAttribute("open", "");
  };
  HTMLDialogElement.prototype.close = function (this: HTMLDialogElement) {
    this.removeAttribute("open");
  };
}
