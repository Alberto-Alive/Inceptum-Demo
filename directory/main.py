from __future__ import annotations

import os
from pathlib import Path

from lablinks_poc.directory_app import create_app


DEFAULT_DB_PATH = Path(__file__).resolve().parent / "data" / "directory.sqlite"

app = create_app(db_path=os.getenv("LABLINKS_DIRECTORY_DB", str(DEFAULT_DB_PATH)))

