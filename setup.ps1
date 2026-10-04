# Run once from this folder:  powershell -ExecutionPolicy Bypass -File .\setup.ps1
# Creates the virtual environment, installs requirements, starts a Git repo and opens VS Code.
# It only touches this folder and starts no build, so anything already running is left alone.
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
if (-not (Test-Path .venv)) { py -3 -m venv .venv }
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
if (-not (Test-Path .git)) { git init -b main | Out-Null }
git add -A
git status --short
if (Get-Command code -ErrorAction SilentlyContinue) { code . } else { Write-Host "VS Code not on PATH. Open this folder in VS Code and pick the .venv interpreter." }
Write-Host "Ready. Files are staged; commit when you are happy:  git commit -m 'Initial aid flows map'"
