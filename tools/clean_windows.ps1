# The clean-machine checklist (docs/VM_CHECKLIST.md) on Windows, unattended
# (#56). Run by .github/workflows/clean-windows.yml on a fresh GitHub Windows
# runner, which is a clean machine every time: nothing installed by us, no
# workspace, no leftovers. Written for Windows PowerShell 5.1, the shell a
# Windows user gets by default.
#
# Everything it does and sees goes to <Out>/run.log; <Out>/summary.md is the
# record table. Exit 1 if any step failed.
#
# -Install: "pypi" (pip install jobforge), "checkout" (pip install . from this
# clone), or "wheel" (the one .whl in dist/, the exact file a release is about
# to upload; release.yml runs this before any upload).
#
# Not covered here: step 11 in Word itself (the runner has no Office; done on
# Windows 10 with Word on #28) and step 13, the agent run, which needs a person.
param(
    [ValidateSet("pypi", "checkout", "wheel")][string]$Install = "checkout",
    [string]$Out = "clean-windows-out"
)
$ErrorActionPreference = "Continue"
$Repo = Split-Path -Parent $PSScriptRoot
$John = Join-Path $Repo "fixtures\personas\john_smith"
New-Item -ItemType Directory -Force $Out | Out-Null
$Out = (Resolve-Path $Out).Path
$Log = Join-Path $Out "run.log"
$Ws = Join-Path $HOME "jobsearch"
$Results = New-Object System.Collections.ArrayList

function Write-Log([string]$Text) {
    Add-Content -Path $Log -Value $Text -Encoding UTF8
    Write-Host $Text
}

# Run a program the way a user types it; log what it prints. Returns the exit
# code and the output text.
function Run([string]$Exe, [string[]]$CmdArgs) {
    Write-Log ("> " + $Exe + " " + ($CmdArgs -join " "))
    $lines = & $Exe @CmdArgs 2>&1 | ForEach-Object { "$_" }
    $code = $LASTEXITCODE
    foreach ($line in $lines) { Write-Log ("  " + $line) }
    Write-Log ("  (exit " + $code + ")")
    return @{ Code = $code; Text = ($lines -join "`n") }
}

function Need([bool]$Condition, [string]$Message) {
    if (-not $Condition) { throw $Message }
}

function Step([string]$Id, [string]$Title, [scriptblock]$Body) {
    Write-Log ""
    Write-Log ("=== " + $Id + ". " + $Title + " ===")
    try {
        $note = (& $Body) -join " "
        [void]$Results.Add([pscustomobject]@{ Id = $Id; Title = $Title; Result = "pass"; Note = $note })
        Write-Log ("PASS " + $note)
    } catch {
        [void]$Results.Add([pscustomobject]@{ Id = $Id; Title = $Title; Result = "FAIL"; Note = $_.Exception.Message })
        Write-Log ("FAIL " + $_.Exception.Message)
    }
}

function Skip([string]$Id, [string]$Title, [string]$Why) {
    [void]$Results.Add([pscustomobject]@{ Id = $Id; Title = $Title; Result = "not run"; Note = $Why })
    Write-Log ""
    Write-Log ("=== " + $Id + ". " + $Title + " === not run: " + $Why)
}

function Read-Back([string]$Docx) {
    $r = Run "python" @("-c", "import sys; from jobforge.docx import extract_text; sys.stdout.reconfigure(encoding='utf-8'); print(extract_text(sys.argv[1]))", $Docx)
    Need ($r.Code -eq 0) "could not read back $Docx"
    return $r.Text
}

$os = Get-CimInstance Win32_OperatingSystem
Write-Log ("Clean-machine run, " + (Get-Date -Format "yyyy-MM-dd HH:mm") + ", " + $os.Caption + " " + $os.Version)
Write-Log ("PowerShell " + $PSVersionTable.PSVersion + ", install path: " + $Install + ", commit " + $env:GITHUB_SHA)

Step "1" "Clean machine: no jobforge on PATH, no ~/jobsearch" {
    Need (-not (Get-Command jobforge -ErrorAction SilentlyContinue)) "jobforge is already on PATH"
    Need (-not (Test-Path $Ws)) "$Ws already exists"
    "clock " + (Get-Date -Format "yyyy-MM-dd")
}

Step "2" "Python 3.11+ (python --version)" {
    $r = Run "python" @("--version")
    Need ($r.Code -eq 0) "python is not on PATH"
    Need ($r.Text -match "Python 3\.(1[1-9]|[2-9]\d)") "needs Python 3.11 or newer: $($r.Text)"
    $r.Text
}

Step "3" "Install Jobforge ($Install)" {
    if ($Install -eq "pypi") {
        $r = Run "pip" @("install", "jobforge")
    } elseif ($Install -eq "wheel") {
        $wheels = @(Get-ChildItem (Join-Path $Repo "dist") -Filter "*.whl" -ErrorAction SilentlyContinue)
        Need ($wheels.Count -eq 1) "expected one .whl in dist/, found $($wheels.Count)"
        $r = Run "pip" @("install", $wheels[0].FullName)
    } else {
        Push-Location $Repo
        $r = Run "pip" @("install", ".")
        Pop-Location
    }
    Need ($r.Code -eq 0) "pip install failed"
    Need ([bool](Get-Command jobforge -ErrorAction SilentlyContinue)) "jobforge is not on PATH after install"
    "on PATH at " + (Get-Command jobforge).Source
}

Step "4" "jobforge --version" {
    $r = Run "jobforge" @("--version")
    Need ($r.Code -eq 0 -and $r.Text -match "^jobforge \d") "unexpected: $($r.Text)"
    $r.Text
}

Step "5" "jobforge jobs outside a workspace says so, no traceback" {
    Set-Location $HOME
    $r = Run "jobforge" @("jobs")
    Need ($r.Code -ne 0) "expected a non-zero exit"
    Need ($r.Text -match "No Jobforge workspace found") "message missing"
    Need ($r.Text -notmatch "Traceback") "printed a traceback"
    "exit " + $r.Code
}

Step "6" "jobforge init ~/jobsearch, layout matches the README" {
    Set-Location $HOME
    $r = Run "jobforge" @("init", "~/jobsearch")
    Need ($r.Code -eq 0) "init failed"
    Need (Test-Path $Ws) "the workspace is not at $Ws (PowerShell passes ~ literally)"
    foreach ($p in "CLAUDE.md", "AGENTS.md", "profile\profile.toml", "profile\atoms", "profile\pending", "intake", "jobs") {
        Need (Test-Path (Join-Path $Ws $p)) "missing $p"
    }
    "workspace at " + $Ws
}

Step "7" "John Smith's profile and atoms in, init --refresh" {
    Copy-Item (Join-Path $John "profile.toml") (Join-Path $Ws "profile\profile.toml") -Force
    Copy-Item (Join-Path $John "atoms\*.toml") (Join-Path $Ws "profile\atoms") -Force
    $r = Run "jobforge" @("init", "--refresh", "~/jobsearch")
    Need ($r.Code -eq 0) "init --refresh failed"
    "refreshed"
}

Step "8" "jobforge inventory lists John's facts" {
    Set-Location $Ws
    $r = Run "jobforge" @("inventory")
    Need ($r.Code -eq 0) "inventory failed"
    Need ($r.Text -match "Northwind Distribution" -and $r.Text -match "Lakeside Grocery") "John's roles missing"
    "both roles listed"
}

Step "9" "jobforge prepare --from-text posting.txt" {
    Set-Location $Ws
    Copy-Item (Join-Path $John "posting.txt") (Join-Path $Ws "posting.txt")
    $r = Run "jobforge" @("prepare", "--from-text", "posting.txt", "--company", "Prairie Freight Co.", "--title", "Operations Supervisor")
    Need ($r.Code -eq 0) "prepare failed"
    $script:Job = Get-ChildItem (Join-Path $Ws "jobs") -Directory | Where-Object { $_.Name -like "prairie*" } | Select-Object -First 1
    Need ($null -ne $script:Job) "no prairie job folder"
    $script:Job.Name
}

Step "10" "plan.json in, jobforge check prairie, jobforge apply prairie" {
    Set-Location $Ws
    Copy-Item (Join-Path $John "plan.json") (Join-Path $script:Job.FullName "plan.json")
    $r = Run "jobforge" @("check", "prairie")
    Need ($r.Code -eq 0) "check failed"
    $r = Run "jobforge" @("apply", "prairie")
    Need ($r.Code -eq 0) "apply failed"
    foreach ($name in "John_Smith_Resume.docx", "John_Smith_Cover_Letter.docx") {
        Need (Test-Path (Join-Path $script:Job.FullName $name)) "missing $name"
    }
    "both .docx written"
}

Step "11" "Both documents read back (Word itself: checked on #28)" {
    foreach ($name in "John_Smith_Resume.docx", "John_Smith_Cover_Letter.docx") {
        $path = Join-Path $script:Job.FullName $name
        Copy-Item $path (Join-Path $Out $name)
        $text = Read-Back $path
        Set-Content -Path (Join-Path $Out ($name + ".txt")) -Value $text -Encoding UTF8
        Need ($text -match "John Smith") "$name does not read back"
    }
    Need ((Read-Back (Join-Path $script:Job.FullName "John_Smith_Cover_Letter.docx")) -match "Prairie Freight") "letter names no employer"
    "text saved next to the .docx files"
}

Step "12" "jobforge applied --mark prairie --status applied; jobs shows it" {
    Set-Location $Ws
    $r = Run "jobforge" @("applied", "--mark", "prairie", "--status", "applied")
    Need ($r.Code -eq 0) "applied --mark failed"
    $r = Run "jobforge" @("jobs")
    Need ($r.Code -eq 0 -and $r.Text -match "applied") "jobs does not show it applied"
    "listed as applied"
}

Skip "13" "Agent run" "needs a person at the keyboard; not part of this unattended run"

# Windows-specific bugs that have bitten before, checked the way a user hits them.
Step "W1" "A posting saved with PowerShell's > (UTF-16) prepares cleanly (#112)" {
    Set-Location $Ws
    Get-Content posting.txt > posting16.txt
    $r = Run "jobforge" @("prepare", "--from-text", "posting16.txt", "--company", "Cedar Mill Foods", "--title", "Shift Supervisor")
    Need ($r.Code -eq 0) "prepare failed"
    Need ($r.Text -notmatch "Windows-1252") "read as Windows-1252"
    $folder = Get-ChildItem (Join-Path $Ws "jobs") -Directory | Where-Object { $_.Name -like "cedar*" } | Select-Object -First 1
    $desc = (Get-Content (Join-Path $folder.FullName "job.json") -Raw -Encoding UTF8 | ConvertFrom-Json).description
    # NUL, the UTF-16 BOM read as Windows-1252 (y-umlaut, thorn), or U+FFFD.
    $junk = "[" + [char]0x0000 + [char]0x00FF + [char]0x00FE + [char]0xFFFD + "]"
    Need ($desc -notmatch $junk) "description holds NUL, BOM bytes, or replacement characters"
    "description reads cleanly"
}

Step "W2" "Output piped to a file with a non-Latin company name (#52)" {
    Set-Location $Ws
    # "Zuerich Uenicode Kabushiki Kaisha" in Latin, accented, and CJK letters,
    # built from code points: PowerShell 5.1 reads a script without a BOM in
    # the ANSI code page, so this file stays ASCII.
    $company = "Z" + [char]0x00FC + "rich " + [char]0x00DC + "n" + [char]0x00EF + "code " +
               [char]0x682A + [char]0x5F0F + [char]0x4F1A + [char]0x793E
    $r = Run "jobforge" @("prepare", "--from-text", "posting.txt", "--company", $company, "--title", "Lead Hand")
    Need ($r.Code -eq 0) "prepare failed"
    jobforge jobs > jobs_out.txt 2>&1
    $code = $LASTEXITCODE
    $text = Get-Content jobs_out.txt -Raw
    Write-Log ("> jobforge jobs > jobs_out.txt  (exit " + $code + ")")
    Write-Log $text
    Need ($code -eq 0) "jobs failed when piped"
    Need ($text -notmatch "Traceback|UnicodeEncodeError") "crashed writing to a pipe"
    "piped output written"
}

Step "W3" "plan.json re-saved by PowerShell with a BOM still checks (#30)" {
    Set-Location $Ws
    $plan = Join-Path $script:Job.FullName "plan.json"
    # Read it whole first: piping Get-Content into Set-Content on the same
    # file holds it open and fails.
    $content = Get-Content $plan -Encoding UTF8
    Set-Content -Path $plan -Value $content -Encoding UTF8
    $bytes = [IO.File]::ReadAllBytes($plan)
    Need ($bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB) "Set-Content did not write a BOM"
    $r = Run "jobforge" @("check", "prairie")
    Need ($r.Code -eq 0) "check failed on a plan with a BOM"
    "passes with a BOM"
}

Step "14" "pip uninstall jobforge leaves the workspace untouched" {
    Set-Location $HOME
    $before = Get-ChildItem $Ws -Recurse -File | Get-FileHash | ForEach-Object { $_.Path + " " + $_.Hash }
    # The README's `pip uninstall jobforge` asks y/n; -y answers it here.
    $r = Run "pip" @("uninstall", "-y", "jobforge")
    Need ($r.Code -eq 0) "uninstall failed"
    Need (-not (Get-Command jobforge -ErrorAction SilentlyContinue)) "jobforge is still on PATH"
    $after = Get-ChildItem $Ws -Recurse -File | Get-FileHash | ForEach-Object { $_.Path + " " + $_.Hash }
    Need ((Compare-Object $before $after) -eq $null) "the workspace changed"
    "$($before.Count) files unchanged"
}

$failed = @($Results | Where-Object { $_.Result -eq "FAIL" })
$lines = @(
    "## Clean-machine run on Windows (#56)",
    "",
    "| Field | Value |", "|---|---|",
    "| Date | $(Get-Date -Format 'yyyy-MM-dd') |",
    "| Machine | GitHub Actions ``windows-latest``, fresh each run |",
    "| OS | $($os.Caption) $($os.Version) |",
    "| Shell | Windows PowerShell $($PSVersionTable.PSVersion) |",
    "| Install path | $Install |",
    "| Commit | $env:GITHUB_SHA |",
    "",
    "| Step | What | Result | Notes |", "|---|---|---|---|"
)
foreach ($r in $Results) { $lines += "| $($r.Id) | $($r.Title) | $($r.Result) | $($r.Note -replace '\|', '/') |" }
$lines += ""
$lines += "$($Results.Count - $failed.Count - @($Results | Where-Object { $_.Result -eq 'not run' }).Count) passed, $($failed.Count) failed. Full transcript: run.log."
Set-Content -Path (Join-Path $Out "summary.md") -Value $lines -Encoding UTF8
if ($env:GITHUB_STEP_SUMMARY) { Add-Content -Path $env:GITHUB_STEP_SUMMARY -Value $lines -Encoding UTF8 }
if ($failed.Count -gt 0) { exit 1 }
exit 0
