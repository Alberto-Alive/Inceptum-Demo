from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from lablinks_poc.directory_app import create_app as create_directory_app
from lablinks_poc.lab_node_app import create_app as create_lab_node_app


ROOT = Path(__file__).resolve().parents[1]
LAB_A_CONFIG = ROOT / "lab_a_node" / "config.json"
LAB_B_CONFIG = ROOT / "lab_b_node" / "config.json"


@pytest.fixture
def directory_client(tmp_path: Path):
    app = create_directory_app(str(tmp_path / "directory.sqlite"))
    with TestClient(app) as client:
        yield client


@pytest.fixture
def lab_a_client(tmp_path: Path):
    app = create_lab_node_app(
        config_path=str(LAB_A_CONFIG),
        db_path=str(tmp_path / "lab_a.sqlite"),
    )
    with TestClient(app) as client:
        yield client


@pytest.fixture
def lab_b_client(tmp_path: Path):
    app = create_lab_node_app(
        config_path=str(LAB_B_CONFIG),
        db_path=str(tmp_path / "lab_b.sqlite"),
    )
    with TestClient(app) as client:
        yield client

