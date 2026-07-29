$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$PythonPath = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $PythonPath)) {
    python -m venv (Join-Path $ProjectRoot ".venv")
    & $PythonPath -m pip install --upgrade pip
    & $PythonPath -m pip install -e $ProjectRoot
}

& $PythonPath -m wslm

