param(
    [string]$Proxy = ""
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$PythonPath = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $PythonPath)) {
    python -m venv (Join-Path $ProjectRoot ".venv")
}

$UpgradeArgs = @("-m", "pip", "install", "--upgrade", "pip")
if ($Proxy) {
    $UpgradeArgs += @("--proxy", $Proxy)
}
& $PythonPath @UpgradeArgs

$InstallArgs = @("-m", "pip", "install", "-e", "$ProjectRoot[dev,build]")
if ($Proxy) {
    $InstallArgs += @("--proxy", $Proxy)
}
& $PythonPath @InstallArgs

& $PythonPath -m pytest

Push-Location $ProjectRoot
try {
    & $PythonPath -m PyInstaller `
        --noconfirm `
        --clean `
        --windowed `
        --onedir `
        --name WSLM `
        --paths (Join-Path $ProjectRoot "src") `
        (Join-Path $ProjectRoot "launcher.py")
}
finally {
    Pop-Location
}

Write-Host "构建完成：$ProjectRoot\dist\WSLM\WSLM.exe"
