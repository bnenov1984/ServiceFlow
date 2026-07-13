"""Regenerate frontend/src/generated/transition-matrix.json from statuses.py.

The client uses this ONLY for UX (dimming forbidden Kanban columns during drag);
the server remains the single validator. A pytest (test_matrix_export.py) fails
CI if the committed JSON drifts from statuses.py — run this script to re-sync:

    uv run python scripts/export_transition_matrix.py
"""

import json
from pathlib import Path

from serviceflow.service_orders.statuses import STATUSES, check_transition


def build_export() -> dict[str, object]:
    codes = list(STATUSES)
    return {
        "statuses": [
            {"code": code, "kind": kind.value, "name_bg": name, "sort": sort}
            for code, (kind, name, sort) in STATUSES.items()
        ],
        "matrix": {
            frm: {to: check_transition(frm, to) for to in codes if to != frm}
            for frm in codes
        },
    }


def main() -> None:
    out = Path(__file__).parents[2] / "frontend" / "src" / "generated"
    out.mkdir(parents=True, exist_ok=True)
    path = out / "transition-matrix.json"
    path.write_text(json.dumps(build_export(), ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")
    print(f"OK: {path}")


if __name__ == "__main__":
    main()
