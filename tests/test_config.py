from __future__ import annotations

from pathlib import Path

from wslm.config import AppConfig, ConfigStore


def test_config_round_trip(tmp_path: Path) -> None:
    store = ConfigStore(tmp_path / "config.json")
    config = AppConfig(
        default_root=r"D:\WSL",
        last_distro="Debian",
        created_environments={"Debian-Dev": r"D:\WSL\Debian-Dev"},
    )
    store.save(config)
    assert store.load() == config


def test_corrupt_config_uses_defaults(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    path.write_text("{broken", encoding="utf-8")
    loaded = ConfigStore(path).load()
    assert loaded.default_root == r"D:\WSL"
    assert loaded.last_distro == "Ubuntu-24.04"

