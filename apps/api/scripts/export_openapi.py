"""Export FastAPI OpenAPI spec to JSON file.

Usage:
    python scripts/export_openapi.py [output_path]

Defaults to writing openapi.json in the project root.
This script does NOT require a running server — it imports the app
directly and extracts the spec at import time.
"""

import json
import sys
from pathlib import Path

# Ensure src/ is importable when running from apps/api/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from coyo.main import app  # noqa: E402

output = sys.argv[1] if len(sys.argv) > 1 else "openapi.json"
spec = app.openapi()

Path(output).write_text(json.dumps(spec, indent=2) + "\n")
print(f"OpenAPI spec written to {output}")
