import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    admin_token: str = field(repr=False)
    viewer_token: str = field(default="", repr=False)
    mode: str = "research"

    def __post_init__(self):
        if len(self.admin_token) < 32:
            raise ValueError("AURA_ADMIN_TOKEN must contain at least 32 characters")
        if self.viewer_token and len(self.viewer_token) < 32:
            raise ValueError("Viewer token must contain at least 32 characters")
        if self.viewer_token == self.admin_token:
            raise ValueError("Admin and viewer tokens must differ")
        if self.mode not in {"research", "virtual"}:
            raise ValueError("Only research and virtual modes are supported; live is prohibited")

    @classmethod
    def from_env(cls):
        return cls(
            Path(os.getenv("AURA_DATA_DIR", "data")),
            os.getenv("AURA_ADMIN_TOKEN", ""),
            os.getenv("AURA_VIEWER_TOKEN", ""),
            os.getenv("AURA_MODE", "research"),
        )
