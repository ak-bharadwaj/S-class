# S-Class V12.1 Plugin Installer for Windows PowerShell
# Run: iex (irm -useb https://raw.githubusercontent.com/ak-bharadwaj/S-class/master/install.ps1)

$ErrorActionPreference = "Stop"

$PluginRoot = "$Home\.gemini\config\plugins"
$PluginDir = "$PluginRoot\sclass-v5"

if (-not (Test-Path $PluginRoot)) {
    New-Item -ItemType Directory -Force -Path $PluginRoot | Out-Null
}

if (Test-Path $PluginDir) {
    Write-Host "Updating S-Class V12.1 Engineering Pipeline Plugin..." -ForegroundColor Green
    git -C "$PluginDir" pull
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ Error: Failed to pull latest git changes." -ForegroundColor Red
        exit $LASTEXITCODE
    }
} else {
    Write-Host "Cloning S-Class V12.1 Engineering Pipeline Plugin..." -ForegroundColor Green
    git clone https://github.com/ak-bharadwaj/S-class.git "$PluginDir"
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ Error: Failed to clone git repository." -ForegroundColor Red
        exit $LASTEXITCODE
    }
}

# Install Python Requirements if available
if (Get-Command python -ErrorAction SilentlyContinue) {
    Write-Host "Verifying Python dependencies..." -ForegroundColor Cyan
    python -m pip install -q -r "$PluginDir\requirements.txt"
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ Error: Failed to install Python dependencies via pip." -ForegroundColor Red
        exit $LASTEXITCODE
    }
}

Write-Host "==========================================================" -ForegroundColor Green
Write-Host "⚡ S-Class V12.1 Installation Complete!" -ForegroundColor Green
Write-Host "Active Plugin Path: $PluginDir" -ForegroundColor Yellow
Write-Host "Cataloged Skills: 118 (Impeccable, Taste, Emil Kowalski, Specification Synthesis, Heavy Backend)" -ForegroundColor Cyan
Write-Host "Subagent Matrix: 8 Concurrent Subagents (find-skill Enabled)" -ForegroundColor Cyan
Write-Host "Commands: /goal, /grill, /doubt, /inquire" -ForegroundColor Magenta
Write-Host "==========================================================" -ForegroundColor Green
