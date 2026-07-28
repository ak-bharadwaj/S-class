# S-Class V10.0 Plugin Installer for Windows PowerShell
# Run: iex (irm -useb https://raw.githubusercontent.com/ak-bharadwaj/S-class/master/install.ps1)

$PluginRoot = "$Home\.gemini\config\plugins"
$PluginDir = "$PluginRoot\sclass-v5"

if (-not (Test-Path $PluginRoot)) {
    New-Item -ItemType Directory -Force -Path $PluginRoot | Out-Null
}

if (Test-Path $PluginDir) {
    Write-Host "Updating S-Class V10.0 Engineering Pipeline Plugin..." -ForegroundColor Green
    git -C "$PluginDir" pull
} else {
    Write-Host "Cloning S-Class V10.0 Engineering Pipeline Plugin..." -ForegroundColor Green
    git clone https://github.com/ak-bharadwaj/S-class.git "$PluginDir"
}

Write-Host "S-Class V10.0 installation complete! Plugin active at $PluginDir" -ForegroundColor Green
