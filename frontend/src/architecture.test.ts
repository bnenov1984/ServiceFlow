/**
 * Frontend boundary check (Business OS Phase 2, docs/business-os/04 §2 rule R9).
 *
 * R9 as originally proposed ("feature folders never import each other's
 * internals") does not hold today: auth/customers/dashboard/intake/order/
 * orders/shell share real, working components across each other (e.g.
 * customers -> order/ContactsSection, orders -> order/dialogs, order/shell
 * -> auth/AuthContext). This is legitimate reuse inside a single vertical
 * with no second module's frontend to protect against yet (docs/business-os/
 * 09 Q7, still Open) — enforcing "never" now would require either breaking
 * the build or an allowlist covering most of the app, which is not a real
 * guard rail. See docs/business-os/12_PHASE_1_IMPLEMENTATION.md's ratchet
 * requirement: only enforce what already holds.
 *
 * What DOES hold today, and is the frontend's actual analogue to the
 * backend's R2 (shared_kernel is the bottom layer — docs/business-os/04 §1):
 * the shared/leaf directories never import from a feature folder. That is
 * the boundary this file protects — it is what would let a future module's
 * UI reuse lib/components/i18n/generated without inheriting ServiceFlow-
 * specific coupling.
 *
 * Enumerates files via Vite's native `import.meta.glob` rather than Node's
 * `fs` — this repo has no `@types/node` and `tsconfig.json` scopes `types`
 * to `vite/client` only; glob avoids adding a dependency for one test file.
 */

import { describe, expect, it } from "vitest";

// Update these two lists whenever a top-level src/ folder is added, removed,
// or renamed — the completeness test below fails loudly if they drift from
// the real folder listing.
const LEAF_DIRS = ["lib", "components", "i18n", "generated"];
const FEATURE_FOLDERS = ["auth", "customers", "dashboard", "intake", "order", "orders", "shell"];

const ALL_SOURCE_FILES = import.meta.glob("./**/*.{ts,tsx}", {
  eager: true,
  query: "?raw",
  import: "default",
}) as Record<string, string>;

function topLevelDir(path: string): string {
  const parts = path.replace(/^\.\//, "").split("/");
  return parts.length > 1 ? parts[0] : "";
}

const FEATURE_FOLDER_IMPORT = new RegExp(
  `from\\s+["'](?:\\.\\./)+(${FEATURE_FOLDERS.join("|")})(?:/|["'])`,
);

describe("frontend architecture: leaf directories stay leaf-level", () => {
  it("LEAF_DIRS + FEATURE_FOLDERS match the real top-level src/ folders", () => {
    const actual = [...new Set(Object.keys(ALL_SOURCE_FILES).map(topLevelDir))]
      .filter((d) => d !== "")
      .sort();
    const declared = [...LEAF_DIRS, ...FEATURE_FOLDERS].sort();
    expect(actual).toEqual(declared);
  });

  for (const leaf of LEAF_DIRS) {
    it(`${leaf}/ does not import from any feature folder`, () => {
      const violations: string[] = [];
      for (const [path, text] of Object.entries(ALL_SOURCE_FILES)) {
        if (topLevelDir(path) !== leaf) continue;
        const match = text.match(FEATURE_FOLDER_IMPORT);
        if (match) {
          violations.push(`${path}: imports from "${match[1]}" (${match[0].trim()})`);
        }
      }
      expect(violations).toEqual([]);
    });
  }
});
