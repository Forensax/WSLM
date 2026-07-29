from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class OnlineDistro:
    name: str
    friendly_name: str


@dataclass(frozen=True, slots=True)
class InstalledDistro:
    name: str
    state: str
    version: str
    is_default: bool = False

    @property
    def state_label(self) -> str:
        labels = {
            "Running": "运行中",
            "Stopped": "已停止",
            "Installing": "安装中",
            "Uninstalling": "卸载中",
            "正在运行": "运行中",
            "已停止": "已停止",
            "正在安装": "安装中",
            "正在卸载": "卸载中",
        }
        return labels.get(self.state, self.state or "未知")

    @property
    def is_running(self) -> bool:
        return self.state in {"Running", "正在运行", "运行中"}

    @property
    def is_busy(self) -> bool:
        lowered = self.state.lower()
        return (
            "install" in lowered
            or "uninstall" in lowered
            or "正在安装" in self.state
            or "正在卸载" in self.state
        )
