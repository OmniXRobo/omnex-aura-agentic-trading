"""Loopback-only interactive dashboard launcher. No services or trading are activated."""

import argparse
import os
import secrets
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path

import uvicorn

from .api import create_app
from .config import Settings


def main():
    parser = argparse.ArgumentParser(description="Open the local OMNEX AURA dashboard")
    parser.add_argument("--data-dir", type=Path, default=Path(os.getenv("AURA_DATA_DIR", "data")))
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--open-browser", action="store_true")
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error("Choose a local port from 1024 to 65535")
    configured = os.getenv("AURA_ADMIN_TOKEN", "")
    token = configured or secrets.token_urlsafe(32)
    settings = Settings(args.data_dir, token, os.getenv("AURA_VIEWER_TOKEN", ""),
                        os.getenv("AURA_MODE", "research"))
    url = f"http://127.0.0.1:{args.port}/dashboard"
    print(f"OMNEX AURA dashboard: {url}", flush=True)
    if not configured:
        print("Temporary local access token (paste into the dashboard; do not share):", flush=True)
        print(token, flush=True)
    else:
        print("Use your configured administrator or viewer token to connect.", flush=True)
    print("Closing this process closes the dashboard. Broker execution remains disabled.", flush=True)
    if args.open_browser:
        def open_when_ready():
            for _ in range(50):
                try:
                    with urllib.request.urlopen(f"http://127.0.0.1:{args.port}/health", timeout=.5) as response:
                        if response.status == 200:
                            webbrowser.open(url)
                            return
                except OSError:
                    pass
                time.sleep(.1)
        threading.Thread(target=open_when_ready, daemon=True).start()
    uvicorn.run(create_app(settings), host="127.0.0.1", port=args.port, access_log=False)


if __name__ == "__main__":
    main()
