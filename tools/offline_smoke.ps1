# Install the offline bundle (#163) on Windows the way a user would: check
# the zip, unzip it, run install.ps1, use jobforge. Also checks that
# install.ps1 refuses a changed wheel. pip is pointed at an index that does
# not exist, so any download fails; install.ps1 also passes --no-index.
#   powershell -ExecutionPolicy Bypass -File tools\offline_smoke.ps1 -Zip bundle\jobforge-offline-X.Y.Z.zip
param([Parameter(Mandatory = $true)][string]$Zip)
$ErrorActionPreference = "Stop"
$Zip = (Resolve-Path $Zip).Path
$work = Join-Path $env:RUNNER_TEMP ("offline-" + [guid]::NewGuid())
if (-not $env:RUNNER_TEMP) { $work = Join-Path $env:TEMP ("offline-" + [guid]::NewGuid()) }

$expected = ((Get-Content (Join-Path (Split-Path $Zip) "SHA256SUMS")) -split "\s+")[0]
if ((Get-FileHash -Algorithm SHA256 $Zip).Hash.ToLower() -ne $expected) {
    throw "the zip does not match SHA256SUMS"
}
Expand-Archive $Zip (Join-Path $work "good")
$dir = (Get-ChildItem (Join-Path $work "good") -Directory)[0].FullName

# A changed wheel must stop install.ps1 before anything is installed.
Copy-Item $dir (Join-Path $work "bad") -Recurse
$wheel = (Get-ChildItem (Join-Path $work "bad\wheels") -Filter *.whl)[0].FullName
Add-Content $wheel "x"
powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $work "bad\install.ps1")
if ($LASTEXITCODE -eq 0) { throw "install.ps1 installed a wheel that does not match SHA256SUMS" }

$env:PIP_INDEX_URL = "http://127.0.0.1:9/simple"
$env:PIP_NO_INDEX = "1"
powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $dir "install.ps1")
if ($LASTEXITCODE -ne 0) { throw "install.ps1 failed" }
jobforge --version
if ($LASTEXITCODE -ne 0) { throw "jobforge --version failed" }
jobforge init (Join-Path $work "ws")
if ($LASTEXITCODE -ne 0) { throw "jobforge init failed" }
if (-not (Test-Path (Join-Path $work "ws\CLAUDE.md"))) { throw "init wrote no CLAUDE.md" }
Write-Host "offline install OK"
