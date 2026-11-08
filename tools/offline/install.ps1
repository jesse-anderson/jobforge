# Install Jobforge {version} from this folder, without the internet (#163).
# Checks the wheel against SHA256SUMS first and stops if it does not match.
#   powershell -ExecutionPolicy Bypass -File install.ps1
param([string]$Python = "python")
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path

$lines = @(Get-Content (Join-Path $here "SHA256SUMS") | Where-Object { $_.Trim() })
if ($lines.Count -eq 0) {
    Write-Host "error: SHA256SUMS is empty; not installing."
    exit 1
}
foreach ($line in $lines) {
    $parts = $line -split "\s+", 2
    $path = Join-Path $here ($parts[1].TrimStart("*"))
    if (-not (Test-Path -LiteralPath $path)) {
        Write-Host "error: $($parts[1]) is missing; the bundle is incomplete."
        exit 1
    }
    $actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $path).Hash.ToLower()
    if ($actual -ne $parts[0].ToLower()) {
        Write-Host "error: $($parts[1]) does not match SHA256SUMS; the bundle is damaged or was changed."
        Write-Host "Download it again from https://github.com/jesse-anderson/jobforge/releases"
        exit 1
    }
    Write-Host "$($parts[1]): OK"
}

& $Python -m pip install --upgrade --no-index --find-links (Join-Path $here "wheels") jobforge
if ($LASTEXITCODE -ne 0) {
    Write-Host "error: pip could not install Jobforge (exit $LASTEXITCODE)."
    exit 1
}
Write-Host "Installed Jobforge {version}. Next: jobforge init ~/jobsearch"
