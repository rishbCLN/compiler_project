"""
Shared pytest fixtures.

`live_server` boots the real FastAPI app (api.server:app) via uvicorn on an
ephemeral port in a background thread, waits until /api/health responds, yields
the base URL, and shuts the server down cleanly on teardown. Used by the
headless Playwright UI suite in tests/ui/.
"""

import socket
import threading
import time

import pytest


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="session")
def live_server():
    import uvicorn
    import urllib.request

    port = _free_port()
    base_url = f"http://127.0.0.1:{port}"

    config = uvicorn.Config("api.server:app", host="127.0.0.1", port=port,
                            log_level="warning", loop="asyncio")
    server = uvicorn.Server(config)

    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    # Poll /api/health until the server is ready (max ~10s).
    deadline = time.time() + 10
    ready = False
    while time.time() < deadline:
        if getattr(server, "started", False):
            try:
                with urllib.request.urlopen(f"{base_url}/api/health", timeout=1) as r:
                    if r.status == 200:
                        ready = True
                        break
            except Exception:
                pass
        time.sleep(0.1)

    if not ready:
        server.should_exit = True
        thread.join(timeout=5)
        pytest.fail("live_server failed to start within timeout")

    yield base_url

    server.should_exit = True
    thread.join(timeout=5)
