"""Dump the OpenAPI schema to packages/core/openapi.json.

Runs without a server so CI can regenerate the TypeScript types and check that
the committed ones are still in sync.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.main import app  # noqa: E402

OUTPUT = Path(__file__).resolve().parents[3] / "packages" / "core" / "openapi.json"


def main() -> None:
    schema = app.openapi()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(schema, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{OUTPUT.relative_to(Path.cwd()) if OUTPUT.is_relative_to(Path.cwd()) else OUTPUT}")
    print(f"  {len(schema['paths'])} endpoint, {len(schema['components']['schemas'])} sema")


if __name__ == "__main__":
    main()
