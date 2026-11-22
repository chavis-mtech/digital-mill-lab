"""Export the FastAPI OpenAPI schema to a JSON file (used by `make contracts`).

Run from apps/ai-api with its venv:  python ../../packages/contracts/scripts/export_openapi.py <out.json>
Imports the app factory only; it does not need a seeded database.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> int:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("openapi.json")
    api_dir = Path(__file__).resolve().parents[3] / "apps" / "ai-api"
    sys.path.insert(0, str(api_dir))
    from app.main import create_app  # noqa: PLC0415

    spec = create_app().openapi()
    out.write_text(json.dumps(spec, indent=2, ensure_ascii=False, sort_keys=False) + "\n", encoding="utf-8")
    print(f"wrote {out} ({len(spec.get('paths', {}))} paths, {len(spec.get('components', {}).get('schemas', {}))} schemas)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
