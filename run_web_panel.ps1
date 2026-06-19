param()

$ErrorActionPreference = "Stop"

$ProjectRoot = $PSScriptRoot
. (Join-Path $ProjectRoot "scripts\python_env.ps1")

$VenvPython = Initialize-ProjectPythonEnvironment -ProjectRoot $ProjectRoot -Prefix "web-panel"
$MainScript = Join-Path $ProjectRoot "web_panel.py"

Write-BootstrapStep "web-panel" "Open http://127.0.0.1:8765 in your browser."
Invoke-BootstrapChecked $VenvPython @($MainScript)
