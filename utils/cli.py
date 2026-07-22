"""Small CLI presentation helpers shared by phase entry points."""

import json
import sys
from typing import Any


def print_json(value: Any) -> None:
    json.dump(value, sys.stdout, indent=2, sort_keys=True, ensure_ascii=False)
    sys.stdout.write("\n")
