$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$tool = Join-Path $root "commands\Invoke-SafeLogAppend.ps1"
function Fail([string]$Message) {
    Write-Output "FAIL: $Message"
    if ($script:LastOutput) { $script:LastOutput | Write-Output }
    exit 1
}

function Invoke-Tool([string[]]$Arguments) {
    $script:LastOutput = & powershell.exe -NoProfile -File $tool @Arguments
    return $LASTEXITCODE
}

$code = Invoke-Tool @("-SelfTest")
if ($code -ne 0) { Fail "self-test exit $code" }

$dir = Join-Path $env:TEMP ("cw-alarm-ps-test-" + [Guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $dir | Out-Null
try {
    $log = Join-Path $dir "application.log"
    $utf8 = New-Object System.Text.UTF8Encoding $false
    [System.IO.File]::WriteAllText($log, "keep this line`n", $utf8)
    $before = [System.IO.File]::ReadAllBytes($log)
    $code = Invoke-Tool @("-LogFile", $log, "-Marker", "ERROR", "-Operator", "tester")
    if ($code -ne 0) { Fail "dry-run exit $code" }
    $mid = [System.IO.File]::ReadAllBytes($log)
    if ($before.Length -ne $mid.Length) { Fail "dry-run changed size" }
    $code = Invoke-Tool @("-LogFile", $log, "-Marker", "ERROR", "-Operator", "tester", "-ConfirmAppend")
    if ($code -ne 0) { Fail "append exit $code" }
    $text = [System.IO.File]::ReadAllText($log, $utf8)
    if (-not $text.StartsWith("keep this line`n")) { Fail "prefix lost" }
    if (-not $text.Contains("marker=ERROR")) { Fail "marker missing" }
    if (-not $text.EndsWith("`n")) { Fail "no trailing newline" }

    $missing = Join-Path $dir "missing.log"
    $code = Invoke-Tool @("-LogFile", $missing, "-Marker", "ERROR", "-Operator", "tester", "-ConfirmAppend")
    if ($code -ne 2) { Fail "missing exit $code" }
    if (Test-Path -LiteralPath $missing) { Fail "missing file was created" }

    $draft = Join-Path $dir "draft.txt"
    [System.IO.File]::WriteAllBytes($draft, [Text.Encoding]::UTF8.GetBytes("draft line one`ndraft line two`r`n"))
    $code = Invoke-Tool @("-LogFile", $log, "-TextFile", $draft, "-ConfirmAppend")
    if ($code -ne 0) { Fail "long exit $code" }
    $long = [System.IO.File]::ReadAllText($log, $utf8)
    if (-not $long.Contains("draft line two`n")) { Fail "long text missing" }
    if (-not $long.StartsWith("keep this line`n")) { Fail "prefix lost after long text" }
    $draftAfter = [System.IO.File]::ReadAllBytes($draft)
    $draftExpected = [Text.Encoding]::UTF8.GetBytes("draft line one`ndraft line two`r`n")
    if ($draftAfter.Length -ne $draftExpected.Length) { Fail "draft was modified" }

    $code = Invoke-Tool @("-LogFile", $log, "-TextFile", $log, "-ConfirmAppend")
    if ($code -ne 2) { Fail "self-append exit $code" }

    $bare = Join-Path $dir "bare.log"
    [System.IO.File]::WriteAllBytes($bare, [Text.Encoding]::UTF8.GetBytes("no newline"))
    $code = Invoke-Tool @("-LogFile", $bare, "-Marker", "ERROR", "-Operator", "tester", "-ConfirmAppend")
    if ($code -ne 2) { Fail "bare exit $code" }
    $bareAfter = [System.IO.File]::ReadAllText($bare, $utf8)
    if ($bareAfter -ne "no newline") { Fail "bare file changed" }
}
finally {
    if ($dir.Contains("cw-alarm-ps-test-")) {
        Remove-Item -LiteralPath $dir -Recurse -Force
    }
}
Write-Output "PASS"
