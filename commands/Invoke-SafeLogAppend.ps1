# Append one UTF-8 test record to an existing log.
# Never creates, truncates, rewrites, or deletes the target.
# A write happens only with -ConfirmAppend.
[CmdletBinding()]
param(
    [string]$LogFile,
    [string]$Marker,
    [string]$Operator,
    [string]$TextFile,
    [switch]$ConfirmAppend,
    [switch]$SelfTest,
    [int]$MaxBytes = 16384
)

$ErrorActionPreference = "Stop"
$AbsoluteMax = 1048550

function Emit([string]$Text) {
    Write-Output $Text
}

function Refuse([string]$Message) {
    Emit "RESULT=REFUSED"
    Emit $Message
    exit 2
}

function Verify-Fail([string]$Message) {
    Emit "RESULT=VERIFY_FAILED"
    Emit $Message
    exit 3
}

function Test-Placeholder([string]$Value) {
    return $Value.Contains([string][char]0x3053 + [string][char]0x3053 + [string][char]0x3092)
}

function Get-Sha256Text([string]$Value) {
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        $bytes = [System.Text.Encoding]::UTF8.GetBytes($Value)
        $hash = $sha.ComputeHash($bytes)
        return ([System.BitConverter]::ToString($hash)).Replace("-", "").ToLowerInvariant()
    }
    finally {
        $sha.Dispose()
    }
}

function Assert-ExistingFile([string]$Path, [string]$Label) {
    if ([string]::IsNullOrWhiteSpace($Path)) {
        Refuse "$Label が空です。"
    }
    if ($Path.Contains("`n") -or $Path.Contains("`r")) {
        Refuse "$Label に改行は使えません。"
    }
    if ($Path.IndexOfAny(@("*", "?", "[")) -ge 0) {
        Refuse "$Label にワイルドカードは使えません。"
    }
    if (-not [System.IO.Path]::IsPathRooted($Path)) {
        Refuse "$Label は絶対パスだけを受け付けます。"
    }
    $full = [System.IO.Path]::GetFullPath($Path)
    $root = [System.IO.Path]::GetFullPath($env:SystemRoot)
    if ($full.Equals($root, [StringComparison]::OrdinalIgnoreCase) -or $full.StartsWith($root + "\", [StringComparison]::OrdinalIgnoreCase)) {
        Refuse "$Label が Windows のシステムディレクトリです。"
    }
    $base = [System.IO.Path]::GetFileNameWithoutExtension($full).ToUpperInvariant()
    $devices = @("CON", "PRN", "AUX", "NUL", "COM1", "COM2", "COM3", "COM4", "LPT1", "LPT2", "LPT3")
    if ($devices -contains $base) {
        Refuse "$Label がデバイス名です。"
    }
    if (-not (Test-Path -LiteralPath $full)) {
        Refuse "$Label のファイルがありません。新しいファイルは作りません。"
    }
    $item = Get-Item -LiteralPath $full -Force
    if ($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) {
        Refuse "$Label はリンクです。本物のファイルのパスを指定します。"
    }
    if ($item.PSIsContainer) {
        Refuse "$Label はディレクトリです。"
    }
    return $item
}

function Read-PrefixAndLast([string]$Path) {
    $stream = [System.IO.File]::Open($Path, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, [System.IO.FileShare]::ReadWrite)
    try {
        $length = $stream.Length
        $count = [Math]::Min(65536, $length)
        $head = New-Object byte[] $count
        $read = 0
        while ($read -lt $count) {
            $n = $stream.Read($head, $read, $count - $read)
            if ($n -le 0) { break }
            $read += $n
        }
        $last = -1
        if ($length -gt 0) {
            [void]$stream.Seek($length - 1, [System.IO.SeekOrigin]::Begin)
            $last = $stream.ReadByte()
        }
        return @{ Length = $length; Head = $head; Last = $last }
    }
    finally {
        $stream.Dispose()
    }
}

function New-MarkerLine([string]$MarkerValue, [string]$OperatorValue) {
    if ([string]::IsNullOrWhiteSpace($MarkerValue)) { Refuse "検知文字列が空です。" }
    if ([string]::IsNullOrWhiteSpace($OperatorValue)) { Refuse "操作者が空です。" }
    if ($MarkerValue.Contains("`n") -or $MarkerValue.Contains("`r")) { Refuse "検知文字列に改行は使えません。長文は -TextFile です。" }
    if ($OperatorValue.Contains("`n") -or $OperatorValue.Contains("`r")) { Refuse "操作者に改行は使えません。" }
    if (Test-Placeholder $MarkerValue) { Refuse "検知文字列に例文が残っています。" }
    if (Test-Placeholder $OperatorValue) { Refuse "操作者に例文が残っています。" }
    $now = [DateTime]::UtcNow.ToString("yyyy-MM-ddTHH:mm:ssZ")
    $id = [Guid]::NewGuid().ToString()
    $hostName = [Environment]::MachineName
    return "CWALARM-TEST time=$now host=$hostName operator=$OperatorValue id=$id marker=$MarkerValue`n"
}

function Convert-ToPayload([string]$Text) {
    $Text = $Text.Replace("`r`n", "`n").Replace("`r", "`n")
    if ($Text.Trim("`n").Length -eq 0) { Refuse "追記する中身が空です。" }
    return $Text.TrimEnd("`n") + "`n"
}

function Show-Plan([string]$Path, [string]$Payload, [bool]$Writing, [long]$SizeBefore) {
    Emit "path=$Path"
    Emit "size_before=$SizeBefore"
    $bytes = [System.Text.Encoding]::UTF8.GetByteCount($Payload)
    Emit "payload_bytes=$bytes"
    Emit "payload_sha256=$(Get-Sha256Text $Payload)"
    Emit "---- payload ----"
    Emit $Payload.TrimEnd("`n")
    Emit "---- end ----"
    if ($Writing) {
        Emit "mode=confirm-append"
    }
    else {
        Emit "RESULT=DRY_RUN"
        Emit "ファイルは変更していません。"
    }
}

function Add-Payload([System.IO.FileInfo]$Item, [string]$Payload) {
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($Payload)
    if ($bytes.Length -gt $MaxBytes) {
        Refuse "追記データが $($bytes.Length) バイトあります。上限は $MaxBytes バイトです。"
    }
    if ($bytes.Length -eq 0 -or $bytes[$bytes.Length - 1] -ne 10) {
        Refuse "試験行の末尾に改行がありません。"
    }
    $beforeInfo = Read-PrefixAndLast $Item.FullName
    if ($beforeInfo.Head.Length -ge 2) {
        if (($beforeInfo.Head[0] -eq 0xFF -and $beforeInfo.Head[1] -eq 0xFE) -or ($beforeInfo.Head[0] -eq 0xFE -and $beforeInfo.Head[1] -eq 0xFF)) {
            Refuse "UTF-16 のファイルです。UTF-8 を混ぜません。"
        }
    }
    if ($beforeInfo.Length -gt 0 -and $beforeInfo.Last -ne 10) {
        Refuse "末尾が改行（0a）ではありません。未完成の行と試験行がつながることがあります。"
    }
    $created = $Item.CreationTimeUtc
    $mutexName = "Local\cw-alarm-append-" + (Get-Sha256Text $Item.FullName)
    $mutex = New-Object System.Threading.Mutex($false, $mutexName)
    $locked = $false
    try {
        $locked = $mutex.WaitOne(10000)
        if (-not $locked) { Refuse "別の処理がロックを持っています。10秒待っても取れなかったので、何も書きません。" }
        Show-Plan $Item.FullName $Payload $true $beforeInfo.Length
        $stream = New-Object System.IO.FileStream(
            $Item.FullName,
            [System.IO.FileMode]::Append,
            [System.IO.FileAccess]::Write,
            [System.IO.FileShare]::ReadWrite)
        try {
            $stream.Write($bytes, 0, $bytes.Length)
            $stream.Flush($true)
        }
        finally {
            $stream.Dispose()
        }
    }
    finally {
        if ($locked) { [void]$mutex.ReleaseMutex() }
        $mutex.Dispose()
    }
    $afterItem = Get-Item -LiteralPath $Item.FullName -Force
    if ($afterItem.CreationTimeUtc -ne $created) {
        Verify-Fail "ファイルの作成時刻が変わりました。置き換わった可能性があるので、戻す操作はしません。"
    }
    if ($afterItem.Length -lt $beforeInfo.Length) {
        Verify-Fail "サイズが減りました。切り詰めが起きました。ツールから戻す操作はしません。"
    }
    if ($afterItem.Length -lt ($beforeInfo.Length + $bytes.Length)) {
        Verify-Fail "増えたバイト数が、書いたバイト数より少ないです。"
    }
    $afterInfo = Read-PrefixAndLast $Item.FullName
    $same = $true
    if ($afterInfo.Head.Length -lt $beforeInfo.Head.Length) { $same = $false }
    else {
        for ($i = 0; $i -lt $beforeInfo.Head.Length; $i++) {
            if ($afterInfo.Head[$i] -ne $beforeInfo.Head[$i]) { $same = $false; break }
        }
    }
    if (-not $same) {
        Verify-Fail "先頭サンプルが変わっています。追記以外の書き換えが起きた可能性があります。"
    }
    Emit "RESULT=APPENDED"
    Emit "size_before=$($beforeInfo.Length)"
    Emit "size_after=$($afterItem.Length)"
    Emit "size_delta=$($afterItem.Length - $beforeInfo.Length)"
    Emit "payload_bytes=$($bytes.Length)"
    Emit "head_unchanged=yes"
}

function Invoke-SelfTest {
    $dir = Join-Path $env:TEMP ("cw-alarm-self-test-" + [Guid]::NewGuid().ToString("N"))
    New-Item -ItemType Directory -Path $dir | Out-Null
    try {
        $log = Join-Path $dir "application.log"
        $utf8 = New-Object System.Text.UTF8Encoding $false
        [System.IO.File]::WriteAllText($log, "existing application line`n", $utf8)
        $before = [System.IO.File]::ReadAllBytes($log)
        $payload = New-MarkerLine "SELFTEST" "self-test"
        $item = Get-Item -LiteralPath $log
        Show-Plan $log $payload $false $item.Length
        $mid = [System.IO.File]::ReadAllBytes($log)
        if ($before.Length -ne $mid.Length) {
            Verify-Fail "ドライランでファイルが変わりました。"
        }
        for ($i = 0; $i -lt $before.Length; $i++) {
            if ($before[$i] -ne $mid[$i]) { Verify-Fail "ドライランでファイルが変わりました。" }
        }
        Add-Payload $item $payload
        $after = [System.IO.File]::ReadAllText($log, $utf8)
        if (-not $after.StartsWith("existing application line`n")) {
            Verify-Fail "セルフテストで既存行が失われました。"
        }
        if (-not $after.EndsWith($payload)) {
            Verify-Fail "セルフテストの追記バイトが一致しません。"
        }
    }
    finally {
        if ($dir.Contains("cw-alarm-self-test-")) {
            Remove-Item -LiteralPath $dir -Recurse -Force
        }
    }
    Emit "RESULT=SELF_TEST_OK"
}

if ($MaxBytes -lt 1 -or $MaxBytes -gt $AbsoluteMax) {
    Refuse "-MaxBytes が範囲外です。"
}
if ($SelfTest) {
    if ($LogFile -or $Marker -or $TextFile -or $ConfirmAppend) {
        Refuse "-SelfTest は単独で実行します。"
    }
    Invoke-SelfTest
    exit 0
}
if (Test-Placeholder $LogFile) { Refuse "ログのパスに例文が残っています。" }
$item = Assert-ExistingFile $LogFile "ログ"
$markerSet = -not [string]::IsNullOrWhiteSpace($Marker)
$textSet = -not [string]::IsNullOrWhiteSpace($TextFile)
if (($markerSet -and $textSet) -or (-not $markerSet -and -not $textSet)) {
    Refuse "-Marker か -TextFile を、どちらか1つ指定します。"
}
if ($markerSet) {
    $payload = New-MarkerLine $Marker $Operator
}
else {
    if (Test-Placeholder $TextFile) { Refuse "下書きパスに例文が残っています。" }
    $draft = Assert-ExistingFile $TextFile "下書き"
    if ($draft.FullName -eq $item.FullName) {
        Refuse "下書きとログが同じファイルです。ログを自分自身へ足すと、終わりなく膨らみます。"
    }
    if ($draft.Length -gt $MaxBytes) { Refuse "下書きが大きすぎます。" }
    $raw = [System.IO.File]::ReadAllBytes($draft.FullName)
    foreach ($b in $raw) {
        if ($b -eq 0) { Refuse "下書きにヌル文字があります。" }
    }
    $strict = New-Object System.Text.UTF8Encoding $false, $true
    try {
        $decoded = $strict.GetString($raw)
    }
    catch {
        Refuse "下書きが UTF-8 として読めません。"
    }
    $payload = Convert-ToPayload $decoded
}
if (-not $ConfirmAppend) {
    Show-Plan $item.FullName $payload $false $item.Length
    exit 0
}
Add-Payload $item $payload
exit 0
