from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

import pytest


ROOT = Path(__file__).resolve().parents[1]
HEALTH_URLS = (
    "http://127.0.0.1:8000/health",
    "http://127.0.0.1:8001/health",
    "http://127.0.0.1:8002/health",
)
DEMO_MODULES = (
    "demo.demo_core_flow",
    "demo.demo_within_lab",
    "demo.demo_policy_controls",
    "demo.demo_cross_lab_agents",
)


def docker_available() -> bool:
    if shutil.which("docker") is None:
        return False
    try:
        subprocess.run(
            ["docker", "compose", "version"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return False
    return True


def wait_for_health(url: str, timeout_seconds: float = 60.0) -> None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            with urlopen(url, timeout=2) as response:
                if response.status == 200:
                    return
        except URLError:
            time.sleep(1)
    raise TimeoutError(f"Timed out waiting for {url}")


@pytest.mark.integration
def test_docker_compose_and_demos_smoke() -> None:
    if os.environ.get("RUN_DOCKER_SMOKE") != "1":
        pytest.skip("Set RUN_DOCKER_SMOKE=1 to run Docker smoke coverage.")
    if not docker_available():
        pytest.skip("Docker Compose is not available in this environment.")

    subprocess.run(["docker", "compose", "up", "--build", "-d"], cwd=ROOT, check=True)
    try:
        for url in HEALTH_URLS:
            wait_for_health(url)
        for module_name in DEMO_MODULES:
            subprocess.run([sys.executable, "-m", module_name], cwd=ROOT, check=True)
    finally:
        subprocess.run(["docker", "compose", "down", "-v"], cwd=ROOT, check=True)
