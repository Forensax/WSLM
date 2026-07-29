from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class AppConfig:
    default_root: str = r"D:\WSL"
    last_distro: str = "Ubuntu-24.04"
    created_environments: dict[str, str] = field(default_factory=dict)


class ConfigStore:
    def __init__(self, path: Path | None = None) -> None:
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        self.path = path or base / "WSLM" / "config.json"

    def load(self) -> AppConfig:
        try:
            raw: dict[str, Any] = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return AppConfig()

        created = raw.get("created_environments", {})
        if not isinstance(created, dict):
            created = {}

        return AppConfig(
            default_root=str(raw.get("default_root") or r"D:\WSL"),
            last_distro=str(raw.get("last_distro") or "Ubuntu-24.04"),
            created_environments={
                str(name): str(location)
                for name, location in created.items()
                if name and location
            },
        )

    def save(self, config: AppConfig) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "default_root": config.default_root,
            "last_distro": config.last_distro,
            "created_environments": config.created_environments,
        }
        temp_path = self.path.with_suffix(".tmp")
        temp_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temp_path.replace(self.path)

