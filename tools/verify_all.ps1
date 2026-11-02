# S-Class v6.0.1 - Comprehensive Local Verification Script (PowerShell / Windows)
# Runs all gates as code, clean package install, and complete test suites.

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RootDir = Split-Path -Parent $ScriptDir

Set-Location $RootDir

Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host "  S-Class v6.0.1 Phase H0 Verification Suite (Windows)           " -ForegroundColor Cyan
Write-Host "  Root: $RootDir                                                 " -ForegroundColor Cyan
Write-Host "=================================================================" -ForegroundColor Cyan

# 1. Gate 3: Kernel and Spec Byte Integrity
Write-Host "`n>>> [1/7] Running Gate 3: Kernel & Spec Byte Integrity..." -ForegroundColor Yellow
python tools/gates/gate_kernel_bytes.py
if ($LASTEXITCODE -ne 0) { throw "Gate 3 failed" }

# 2. Gate 4: Golden Vectors Reproduction
Write-Host "`n>>> [2/7] Running Gate 4: Golden Vectors Reproduction..." -ForegroundColor Yellow
python tools/gates/gate_golden_vectors.py
if ($LASTEXITCODE -ne 0) { throw "Gate 4 failed" }

# 3. Gate 5: Documentation Labels and Status Claims
Write-Host "`n>>> [3/7] Running Gate 5: Documentation Status Labels..." -ForegroundColor Yellow
python tools/gates/gate_docs_labels.py
if ($LASTEXITCODE -ne 0) { throw "Gate 5 failed" }

# 4. Gate 6: Environment Variable Audit (Report-Only in H0)
Write-Host "`n>>> [4/7] Running Gate 6: Environment Variable Audit (Report-Only)..." -ForegroundColor Yellow
python tools/gates/gate_env_vars.py
if ($LASTEXITCODE -ne 0) { throw "Gate 6 failed" }

# 5. Gate 1: Wheel Clean-Install Smoke Test
Write-Host "`n>>> [5/7] Running Gate 1: Wheel Clean-Install Smoke Test..." -ForegroundColor Yellow
python tools/gates/gate_wheel_smoke.py
if ($LASTEXITCODE -ne 0) { throw "Gate 1 failed" }

# 6. Conformance & Spec Integrity Check
Write-Host "`n>>> [6/7] Running Spec Integrity Check..." -ForegroundColor Yellow
python 10-CONFORMANCE/spec_integrity.py
if ($LASTEXITCODE -ne 0) { throw "Spec integrity failed" }

# 7. Unit Tests on Windows
Write-Host "`n>>> [7/7] Running Unit & Conformance Test Suite..." -ForegroundColor Yellow
python -m pytest 10-CONFORMANCE/ 20-RUNTIME/ tests/ -v
if ($LASTEXITCODE -ne 0) { throw "Test suite failed" }

Write-Host "`n=================================================================" -ForegroundColor Green
Write-Host "  WINDOWS VERIFICATION COMPLETED (Note: Linux CI governs gates)   " -ForegroundColor Green
Write-Host "=================================================================" -ForegroundColor Green
