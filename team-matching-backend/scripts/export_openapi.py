"""Export an offline API contract, suitable for Postman or frontend code generation."""

import json
from pathlib import Path

from app.main import app

if __name__ == "__main__":
    path = Path(__file__).resolve().parents[1] / "docs" / "openapi.json"
    path.write_text(json.dumps(app.openapi(), indent=2) + "\n")
    print(path)
