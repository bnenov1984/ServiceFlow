"""Export the FastAPI OpenAPI schema for frontend type generation (docs/15 §1).

    uv run python scripts/export_openapi.py
    (cd ../frontend && npm run gen:api)
"""

import json
from pathlib import Path

from serviceflow.main import create_app


def main() -> None:
    schema = create_app().openapi()
    out = Path(__file__).parents[2] / "frontend" / "src" / "generated" / "openapi.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(schema, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"OK: {out}")


if __name__ == "__main__":
    main()
