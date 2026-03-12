from __future__ import annotations

import json
import os

from pydantic import BaseModel


CLAIM_ID = os.getenv("LABLINKS_CLAIM_ID", "lablinks:qsar:auroc:001")
DIRECTORY_URL = os.getenv("LABLINKS_DIRECTORY_URL", "http://localhost:8000")
LAB_A_URL = os.getenv("LABLINKS_LAB_A_URL", "http://localhost:8001")
LAB_B_URL = os.getenv("LABLINKS_LAB_B_URL", "http://localhost:8002")


def render_model(model: BaseModel) -> str:
    return json.dumps(model.model_dump(mode="json"), indent=2, sort_keys=True)


def step(title: str, summary: str) -> None:
    print(f"\n{title}")
    print(f"   {summary}")
