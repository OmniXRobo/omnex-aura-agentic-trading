"""Managed browser QA only. Public fixture tokens protect no operational data."""

import os
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import uvicorn

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aura.api import create_app  # noqa: E402
from aura.config import Settings  # noqa: E402
from aura.dashboard_fixture import seed_dashboard  # noqa: E402

with TemporaryDirectory(prefix="aura-dashboard-preview-") as directory:
    seed_dashboard(directory)
    settings = Settings(Path(directory), "synthetic-dashboard-admin-access-token-only",
                        "synthetic-dashboard-viewer-access-token-only")
    uvicorn.run(create_app(settings), host="0.0.0.0", port=int(os.getenv("PORT", "3000")), access_log=False)
