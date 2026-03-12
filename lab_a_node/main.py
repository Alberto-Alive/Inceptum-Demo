from __future__ import annotations

import os
from pathlib import Path

from lablinks_poc.lab_node_app import create_app


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DB_PATH = BASE_DIR / "data" / "lab_a.sqlite"
DEFAULT_CONFIG_PATH = BASE_DIR / "config.json"

app = create_app(
    config_path=os.getenv("LABLINKS_NODE_CONFIG", str(DEFAULT_CONFIG_PATH)),
    db_path=os.getenv("LABLINKS_NODE_DB", str(DEFAULT_DB_PATH)),
)

