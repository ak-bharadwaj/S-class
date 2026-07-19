# S-Class V5.2 Plugin Installer
# Run: iex (irm -useb https://raw.githubusercontent.com/ak-bharadwaj/S-class/master/install.ps1)

$PluginRoot = "$Home\.gemini\config\plugins"
$PluginDir = "$PluginRoot\sclass-v5"

if (-not (Test-Path $PluginRoot)) {
    New-Item -ItemType Directory -Force -Path $PluginRoot
}

if (Test-Path $PluginDir) {
    Write-Host "Plugin already installed. Updating..." -ForegroundColor Green
    cd $PluginDir
    git pull
} else {
    Write-Host "Cloning S-Class V5.2 Engineering Pipeline Plugin..." -ForegroundColor Green
    git clone https://github.com/ak-bharadwaj/S-class.git $PluginDir
}

Write-Host "Installation complete! Inherit this workflow by adding 'pipeline: sclass-v5' to your CLAUDE.md workspace config." -ForegroundColor Green
