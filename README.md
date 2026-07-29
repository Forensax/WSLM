# WSLM

简洁的 Windows WSL 环境管理器。

## 功能

- 查看可安装和已安装的 WSL 发行版
- 使用自定义名称和目录创建全新 WSL 2 环境
- 打开、停止和删除环境
- 默认将新环境安装到 `D:\WSL`

## 系统要求

- Windows 10 或 Windows 11 x64
- 已安装并更新 WSL：

```powershell
wsl --install --no-distribution
wsl --update
```

## 下载

从 [Releases](https://github.com/Forensax/WSLM/releases) 下载：

- `WSLM-版本-windows-x64.zip`：推荐，解压后运行 `WSLM.exe`
- `WSLM-版本-windows-x64.exe`：单文件版，首次启动可能稍慢

便携 ZIP 中的 `_internal` 目录是运行依赖，请与 `WSLM.exe` 保持在同一目录。

## 源码运行

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\run.ps1
```

## 本地构建

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\build.ps1
```

需要本机代理时：

```powershell
.\build.ps1 -Proxy "http://127.0.0.1:10808"
```

## 注意

删除环境会执行 `wsl --unregister`，其中的文件、软件和设置会被永久删除。操作前请先备份重要数据。
