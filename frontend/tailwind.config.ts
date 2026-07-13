import type { Config } from "tailwindcss";
import { alertColors, statusKindColors } from "./src/theme";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // status-working-bg / status-working-text / status-working-solid, etc.
        ...Object.fromEntries(
          Object.entries(statusKindColors).flatMap(([kind, c]) => [
            [`status-${kind.replace("_", "-")}-bg`, c.bg],
            [`status-${kind.replace("_", "-")}-text`, c.text],
            [`status-${kind.replace("_", "-")}-solid`, c.solid],
          ]),
        ),
        overdue: alertColors.overdue,
        "priority-high": alertColors.priorityHigh,
      },
      minHeight: { touch: "44px" },
      minWidth: { touch: "44px" },
      fontFamily: {
        sans: ["system-ui", "Segoe UI", "Roboto", "sans-serif"],
      },
    },
  },
  plugins: [],
} satisfies Config;
