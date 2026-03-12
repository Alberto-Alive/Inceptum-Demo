from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_claim() -> dict:
    with (ROOT / "examples" / "claim.json").open("r", encoding="utf-8") as handle:
        return json.load(handle)


def test_directory_can_publish_list_fetch_and_search_claims(directory_client) -> None:
    claim = load_claim()

    create_response = directory_client.post("/claims", json=claim)
    assert create_response.status_code == 200
    assert create_response.json()["claim_id"] == claim["claim_id"]

    list_response = directory_client.get("/claims")
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1

    fetch_response = directory_client.get(f"/claims/{claim['claim_id']}")
    assert fetch_response.status_code == 200
    assert fetch_response.json()["owner"]["lab_id"] == "lab-a"

    search_response = directory_client.get("/claims", params={"q": "kinase"})
    assert search_response.status_code == 200
    assert len(search_response.json()) == 1

    empty_search = directory_client.get("/claims", params={"q": "nonexistent"})
    assert empty_search.status_code == 200
    assert empty_search.json() == []

    reset_response = directory_client.post("/demo/reset")
    assert reset_response.status_code == 200
    assert directory_client.get("/claims").json() == []
