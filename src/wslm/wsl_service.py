from __future__ import annotations

import locale
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Iterable, Sequence

from .models import InstalledDistro, OnlineDistro


NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


class WslCommandError(RuntimeError):
    def __init__(self, command: Sequence[str], message: str, returncode: int = 1) -> None:
        super().__init__(message.strip() or "WSL 命令执行失败")
        self.command = tuple(command)
        self.returncode = returncode


def decode_wsl_output(data: bytes) -> str:
    if not data:
        return ""
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return data.decode("utf-16", errors="replace").lstrip("\ufeff")
    if data[:200].count(b"\x00") > max(2, len(data[:200]) // 8):
        return data.decode("utf-16-le", errors="replace").lstrip("\ufeff")

    encodings = ("utf-8", locale.getpreferredencoding(False), "gb18030")
    for encoding in dict.fromkeys(encodings):
        try:
            return data.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            continue
    return data.decode("utf-8", errors="replace")


def parse_online_distros(output: str) -> list[OnlineDistro]:
    distros: list[OnlineDistro] = []
    seen: set[str] = set()
    for raw_line in output.replace("\x00", "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        match = re.match(r"^(\S+)\s{2,}(.+?)\s*$", line)
        if not match:
            continue
        name, friendly_name = match.groups()
        if name.upper() == "NAME" or name in seen:
            continue
        seen.add(name)
        distros.append(OnlineDistro(name=name, friendly_name=friendly_name))
    return distros


def parse_quiet_names(output: str) -> list[str]:
    return [
        line.strip().lstrip("*").strip()
        for line in output.replace("\x00", "").splitlines()
        if line.strip().lstrip("*").strip()
    ]


def parse_installed_distros(
    output: str,
    known_names: Iterable[str] = (),
) -> list[InstalledDistro]:
    names = sorted(set(known_names), key=len, reverse=True)
    distros: list[InstalledDistro] = []

    for raw_line in output.replace("\x00", "").splitlines():
        line = raw_line.strip()
        if not line or line.upper().startswith("NAME"):
            continue

        is_default = line.startswith("*")
        content = line[1:].strip() if is_default else line
        name = ""
        remainder = ""

        for candidate in names:
            if content == candidate:
                name = candidate
                break
            if content.startswith(candidate) and content[len(candidate) : len(candidate) + 1].isspace():
                name = candidate
                remainder = content[len(candidate) :].strip()
                break

        if not name:
            match = re.match(r"^(.+?)\s{2,}(.+?)\s+([12])\s*$", content)
            if not match:
                continue
            name, state, version = match.groups()
            distros.append(
                InstalledDistro(
                    name=name.strip(),
                    state=state.strip(),
                    version=version,
                    is_default=is_default,
                )
            )
            continue

        if not remainder:
            distros.append(InstalledDistro(name=name, state="", version="", is_default=is_default))
            continue

        parts = remainder.split()
        version = parts[-1] if parts and parts[-1] in {"1", "2"} else ""
        state_parts = parts[:-1] if version else parts
        distros.append(
            InstalledDistro(
                name=name,
                state=" ".join(state_parts),
                version=version,
                is_default=is_default,
            )
        )

    return distros


def validate_environment_name(name: str) -> str:
    value = name.strip()
    if not NAME_PATTERN.fullmatch(value):
        raise ValueError("环境名称只能包含字母、数字、点、下划线和短横线，长度为 1–64。")
    return value


def validate_install_location(location: str) -> Path:
    value = location.strip().strip('"')
    if not value:
        raise ValueError("请选择安装目录。")
    path = Path(value)
    if not path.is_absolute() or not path.drive:
        raise ValueError("安装目录必须是 Windows 绝对路径。")
    if str(path) == path.anchor:
        raise ValueError("不能直接使用磁盘根目录。")
    if not Path(path.anchor).exists():
        raise ValueError(f"磁盘不存在：{path.anchor}")
    if path.exists() and any(path.iterdir()):
        raise ValueError("安装目录已存在且不为空。")
    return path


class WslService:
    def __init__(self, executable: str = "wsl.exe") -> None:
        self.executable = executable

    @staticmethod
    def _hidden_process_options() -> dict[str, object]:
        if os.name != "nt":
            return {}
        startup = subprocess.STARTUPINFO()
        startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        return {
            "startupinfo": startup,
            "creationflags": subprocess.CREATE_NO_WINDOW,
        }

    def run(self, args: Sequence[str], timeout: int = 120) -> str:
        command = [self.executable, *args]
        try:
            result = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout,
                check=False,
                **self._hidden_process_options(),
            )
        except FileNotFoundError as exc:
            raise WslCommandError(command, "未找到 wsl.exe，请先安装 WSL。") from exc
        except subprocess.TimeoutExpired as exc:
            raise WslCommandError(command, "WSL 命令执行超时。") from exc

        stdout = decode_wsl_output(result.stdout)
        stderr = decode_wsl_output(result.stderr)
        if result.returncode != 0:
            raise WslCommandError(command, stderr or stdout, result.returncode)
        return stdout

    def list_online(self) -> list[OnlineDistro]:
        return parse_online_distros(self.run(["--list", "--online"], timeout=90))

    def list_installed(self) -> list[InstalledDistro]:
        names = parse_quiet_names(self.run(["--list", "--quiet"], timeout=30))
        if not names:
            return []
        verbose = self.run(["--list", "--verbose"], timeout=30)
        return parse_installed_distros(verbose, names)

    def install(self, distro: str, name: str, location: str) -> Path:
        environment_name = validate_environment_name(name)
        install_path = validate_install_location(location)
        created_here = not install_path.exists()
        install_path.mkdir(parents=True, exist_ok=True)

        try:
            self.run(
                [
                    "--install",
                    distro,
                    "--name",
                    environment_name,
                    "--location",
                    str(install_path),
                    "--version",
                    "2",
                    "--no-launch",
                ],
                timeout=3600,
            )
        except Exception:
            if created_here and install_path.exists() and not any(install_path.iterdir()):
                install_path.rmdir()
            raise
        return install_path

    def terminate(self, name: str) -> None:
        self.run(["--terminate", validate_environment_name(name)], timeout=60)

    def unregister(self, name: str) -> None:
        self.run(["--unregister", validate_environment_name(name)], timeout=300)

    def launch_terminal(self, name: str) -> None:
        environment_name = validate_environment_name(name)
        windows_terminal = shutil.which("wt.exe")
        if windows_terminal:
            subprocess.Popen(
                [
                    windows_terminal,
                    "-w",
                    "0",
                    "new-tab",
                    "--title",
                    environment_name,
                    self.executable,
                    "--distribution",
                    environment_name,
                ],
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
            )
            return

        subprocess.Popen(
            [self.executable, "--distribution", environment_name],
            creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == "nt" else 0,
        )
