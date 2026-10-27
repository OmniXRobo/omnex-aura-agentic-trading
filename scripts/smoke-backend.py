"""Real loopback HTTP/process restart check. Temporary secrets/data are never printed."""

import json
import os
import secrets
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen


def main():
    token = secrets.token_urlsafe(32)
    with tempfile.TemporaryDirectory() as temporary:
        env = os.environ | {
            "AURA_ADMIN_TOKEN": token,
            "AURA_VIEWER_TOKEN": "",
            "AURA_DATA_DIR": temporary,
            "AURA_MODE": "research",
        }
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        base = f"http://127.0.0.1:{port}"

        def request(path, body=None, method=None):
            data = None if body is None else json.dumps(body).encode()
            req = Request(
                base + path,
                data=data,
                method=method,
                headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"},
            )
            with urlopen(req, timeout=2) as response:
                return json.load(response)

        def start():
            process = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "uvicorn",
                    "aura.api:create_app",
                    "--factory",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(port),
                ],
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            for _ in range(100):
                if process.poll() is not None:
                    raise RuntimeError("Backend process exited during startup")
                try:
                    request("/health")
                    return process
                except (URLError, OSError):
                    time.sleep(0.05)
            process.terminate()
            process.wait(timeout=5)
            raise RuntimeError("Backend startup timed out")

        def stop(process):
            process.terminate()
            process.wait(timeout=5)

        process = start()
        try:
            assert request("/v1/status")["kill_switch"] is True
            run = request(
                "/v1/research/run",
                {"prices": [3000, 3001, 3002], "tick_age_seconds": 1, "source": "fixture"},
            )
            assert run["signal"] == "NO TRADE"
            request("/v1/safety/kill-switch", {"enabled": False}, "PUT")
        finally:
            stop(process)
        subprocess.run(
            [sys.executable, "-m", "aura.safety", "--data-dir", temporary],
            check=True,
            capture_output=True,
        )
        process = start()
        try:
            status = request("/v1/status")
            assert status["kill_switch"] is True
            assert status["live_enabled"] is False
            assert len(request("/v1/memory/historical")) == 1
        finally:
            stop(process)
    evidence = {
        "http_process_smoke": "passed",
        "restart_memory": "passed",
        "offline_cli_stop": "passed",
        "live_enabled": False,
    }
    Path("reports/smoke.json").write_text(json.dumps(evidence, indent=2) + "\n")
    print(json.dumps(evidence))


if __name__ == "__main__":
    main()
