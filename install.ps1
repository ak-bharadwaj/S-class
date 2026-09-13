# S-Class V13 Universal Multi-IDE Plugin & Microkernel Installer for Windows PowerShell
# Run: iex (irm -useb https://raw.githubusercontent.com/ak-bharadwaj/S-class/master/install.ps1)

param(
    [string]$Workspace = ""
)

$ErrorActionPreference = "Stop"

$PluginRoot = "$Home\.gemini\config\plugins"
$PluginDir = "$PluginRoot\sclass-v5"

if (-not (Test-Path $PluginRoot)) {
    New-Item -ItemType Directory -Force -Path $PluginRoot | Out-Null
}

if (Test-Path $PluginDir) {
    Write-Host "Updating S-Class V13 Engineering Control Plane Plugin..." -ForegroundColor Green
    git -C "$PluginDir" pull
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ Error: Failed to pull latest git changes." -ForegroundColor Red
        exit $LASTEXITCODE
    }
} else {
    Write-Host "Cloning S-Class V13 Engineering Control Plane Plugin..." -ForegroundColor Green
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

# Detect active target workspace
$TargetWS = $Workspace
if (-not $TargetWS) {
    $TargetWS = (Get-Location).Path
}

# Multi-IDE Detection & Registration
$DetectedIDEs = @()
if (Test-Path "$TargetWS\.cursor") { $DetectedIDEs += "Cursor" }
if (Test-Path "$TargetWS\.claude") { $DetectedIDEs += "Claude Code" }
if (Test-Path "$TargetWS\.agents" -or (Test-Path "$TargetWS\.gemini")) { $DetectedIDEs += "Antigravity / Gemini" }
if (Test-Path "$TargetWS\.codex") { $DetectedIDEs += "OpenAI Codex CLI" }
if (Test-Path "$TargetWS\.github") { $DetectedIDEs += "GitHub Copilot" }
if (Test-Path "$TargetWS\.windsurf") { $DetectedIDEs += "Windsurf" }

if ($DetectedIDEs.Count -eq 0) {
    # Default to registering core ecosystem configurations if clean workspace
    $DetectedIDEs = @("Universal (Cursor, Claude Code, Antigravity, Codex CLI)")
}

# Run sclass init to deploy runner, register MCP configs, and project rules
if (Get-Command python -ErrorAction SilentlyContinue) {
    Write-Host "Registering hooks, MCP server configs, and governance rules in $TargetWS..." -ForegroundColor Cyan
    python "$PluginDir\sclass_cli.py" init -w "$TargetWS"
}

Write-Host "==========================================================" -ForegroundColor Green
Write-Host "⚡ S-Class V13 Universal Installation & Integration Complete!" -ForegroundColor Green
Write-Host "Active Plugin Path: $PluginDir" -ForegroundColor Yellow
Write-Host "Active Workspace:   $TargetWS" -ForegroundColor Yellow
Write-Host "Target IDEs:        $($DetectedIDEs -join ', ')" -ForegroundColor Cyan
Write-Host "Cataloged Skills:   118 (Domain Primitives, Behavior Graph, Spec Synthesis, ADR Architecture Debate)" -ForegroundColor Cyan
Write-Host "Cross-Platform:     Blocking Hooks, MCP Plugin Configs, Rule Parity (.cursorrules, CLAUDE.md, .claude/rules)" -ForegroundColor Cyan
Write-Host "Commands:           /goal, /boost, /learn, /grill, /doubt, /inquire" -ForegroundColor Magenta
Write-Host "==========================================================" -ForegroundColor Green
