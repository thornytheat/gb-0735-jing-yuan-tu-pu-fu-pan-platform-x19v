import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RULE_VERSION = "wafer-1.0.0"
DEFAULT_SAMPLE = "mixed"
MAX_INPUT_BYTES = 2 * 1024 * 1024


def database_path():
    return Path(os.environ.get("WAFER_DB", "wafer-review.sqlite3"))
