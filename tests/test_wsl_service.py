from __future__ import annotations

from pathlib import Path

import pytest

from wslm.models import OnlineDistro
from wslm.wsl_service import (
    WslService,
    decode_wsl_output,
    parse_installed_distros,
    parse_online_distros,
    validate_environment_name,
    validate_install_location,
)


def test_decode_utf16le_output() -> None:
    source = "Ubuntu    Running    2\r\n"
    assert decode_wsl_output(source.encode("utf-16-le")) == source


def test_decode_utf8_output() -> None:
    source = "Ubuntu\nDebian\n"
    assert decode_wsl_output(source.encode("utf-8")) == source


def test_parse_online_distros() -> None:
    output = """以下是可安装的有效分发的列表。
NAME                 FRIENDLY NAME
Ubuntu-24.04         Ubuntu 24.04 LTS
Debian               Debian GNU/Linux
"""
    assert parse_online_distros(output) == [
        OnlineDistro("Ubuntu-24.04", "Ubuntu 24.04 LTS"),
        OnlineDistro("Debian", "Debian GNU/Linux"),
    ]


def test_parse_installed_distros_with_default() -> None:
    output = """  NAME               STATE           VERSION
* Ubuntu             Running         2
  Debian-Test        Stopped         2
"""
    result = parse_installed_distros(output, ["Ubuntu", "Debian-Test"])
    assert [(item.name, item.state, item.version, item.is_default) for item in result] == [
        ("Ubuntu", "Running", "2", True),
        ("Debian-Test", "Stopped", "2", False),
    ]
    assert result[0].is_running is True
    assert result[1].is_running is False


@pytest.mark.parametrize(
    "name",
    ["Ubuntu", "Ubuntu-24.04", "dev_1", "test.env"],
)
def test_validate_environment_name_accepts_safe_names(name: str) -> None:
    assert validate_environment_name(name) == name


@pytest.mark.parametrize(
    "name",
    ["", "has space", "-leading", "名字", "a" * 65],
)
def test_validate_environment_name_rejects_unsafe_names(name: str) -> None:
    with pytest.raises(ValueError):
        validate_environment_name(name)


def test_validate_install_location_rejects_relative_path() -> None:
    with pytest.raises(ValueError):
        validate_install_location("relative/path")


def test_validate_install_location_rejects_nonempty_directory(tmp_path: Path) -> None:
    (tmp_path / "file.txt").write_text("data", encoding="utf-8")
    with pytest.raises(ValueError):
        validate_install_location(str(tmp_path))


def test_list_installed_returns_empty_without_verbose_call() -> None:
    class EmptyService(WslService):
        def __init__(self) -> None:
            self.calls: list[tuple[str, ...]] = []

        def run(self, args: list[str], timeout: int = 120) -> str:
            self.calls.append(tuple(args))
            return ""

    service = EmptyService()
    assert service.list_installed() == []
    assert service.calls == [("--list", "--quiet")]
