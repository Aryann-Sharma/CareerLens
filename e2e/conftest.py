from collections.abc import Generator
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from urllib.error import URLError
from urllib.request import urlopen

import pytest
from playwright.sync_api import Page


PROJECT_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def no_browser_errors(page: Page) -> Generator[None, None, None]:
    errors: list[str] = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    yield
    assert not errors, "Browser errors: " + "; ".join(errors)


def find_available_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


def wait_for_server(process: subprocess.Popen[str], health_url: str) -> None:
    deadline = time.monotonic() + 15

    while time.monotonic() < deadline:
        if process.poll() is not None:
            pytest.fail("The test server stopped before it became ready.")

        try:
            with urlopen(health_url, timeout=1) as response:
                if response.status == 200:
                    return
        except (URLError, TimeoutError):
            time.sleep(0.1)

    pytest.fail("The test server did not become ready within 15 seconds.")


@pytest.fixture(scope="session")
def app_url(tmp_path_factory: pytest.TempPathFactory) -> Generator[str, None, None]:
    test_directory = tmp_path_factory.mktemp("careerlens-e2e")
    database_path = test_directory / "careerlens.db"
    log_path = test_directory / "server.log"
    port = find_available_port()
    url = f"http://127.0.0.1:{port}"

    environment = os.environ.copy()
    environment.update(
        {
            "DATABASE_URL": os.getenv(
                "E2E_DATABASE_URL", f"sqlite:///{database_path.as_posix()}"
            ),
            "ENVIRONMENT": "testing",
            "AUTH_SECRET_KEY": "browser-test-secret-that-is-long-enough",
        }
    )

    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=PROJECT_ROOT,
        env=environment,
        check=True,
    )

    with log_path.open("w", encoding="utf-8") as server_log:
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "backend.app.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
                "--log-level",
                "warning",
            ],
            cwd=PROJECT_ROOT,
            env=environment,
            stdout=server_log,
            stderr=subprocess.STDOUT,
            text=True,
        )

        try:
            wait_for_server(process, f"{url}/health/ready")
            yield url
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
