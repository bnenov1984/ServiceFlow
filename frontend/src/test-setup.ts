import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

// With `globals: false` RTL's automatic cleanup can't self-register.
afterEach(cleanup);
