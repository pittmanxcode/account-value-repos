"""Optional repo-root config (config.yaml). Defaults keep V2 publication
disabled until the well passes its readiness gate and the feature is
explicitly enabled."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class AppConfig:
    batch_size: int = 10
    well_enabled: bool = False  # spec: publication disabled until explicitly enabled
    github_repo: str = "pittmanxcode/account-value-repos"
    well_exports_dir: str = "../factory-buyer-readiness-well/data/exports"
    extra: dict = field(default_factory=dict)


def load_config(root: Path | None = None) -> AppConfig:
    root = root or Path.cwd()
    config_file = root / "config.yaml"
    config = AppConfig()
    if config_file.exists():
        import yaml

        payload = yaml.safe_load(config_file.read_text(encoding="utf-8")) or {}
        for key in ("batch_size", "well_enabled", "github_repo", "well_exports_dir"):
            if key in payload:
                setattr(config, key, payload[key])
        config.extra = {k: v for k, v in payload.items()
                        if k not in {"batch_size", "well_enabled", "github_repo", "well_exports_dir"}}
    return config
