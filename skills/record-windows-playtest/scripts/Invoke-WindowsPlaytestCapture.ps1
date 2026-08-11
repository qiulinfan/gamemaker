#requires -Version 7.0

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('Start', 'Complete')]
    [string]$Action,

    [string]$WindowTitle,
    [string]$OutputDirectory,
    [string]$BaseName = 'playtest',

    [ValidateRange(10, 1800)]
    [int]$DurationSeconds = 180,

    [ValidateRange(15, 60)]
    [int]$Framerate = 30,

    [string]$StatePath,
    [string]$IssueId,
    [string]$Revision,

    [ValidateSet('PASS', 'FAIL', 'BLOCKED')]
    [string]$Verdict,

    [string]$Summary,
    [string]$PublishRoot,
    [string]$PublishBaseUrl,
    [string]$PublishProcessName,
    [switch]$SkipPublish
)

$ErrorActionPreference = 'Stop'
if ($PSVersionTable.PSVersion.Major -lt 7) {
    throw 'Invoke-WindowsPlaytestCapture.ps1 requires PowerShell 7 or newer (pwsh).'
}

function Resolve-MediaTool {
    param([Parameter(Mandatory = $true)][string]$Name)

    $command = Get-Command $Name -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($command) {
        return $command.Source
    }

    $wingetRoot = Join-Path $env:LOCALAPPDATA 'Microsoft\WinGet\Packages'
    if (Test-Path -LiteralPath $wingetRoot) {
        $candidate = Get-ChildItem -LiteralPath $wingetRoot -Recurse -Filter "$Name.exe" -File -ErrorAction SilentlyContinue |
            Where-Object { $_.FullName -like '*Gyan.FFmpeg*' } |
            Sort-Object LastWriteTimeUtc -Descending |
            Select-Object -First 1
        if ($candidate) {
            return $candidate.FullName
        }
    }

    throw "$Name was not found on PATH or in the standard WinGet FFmpeg package directory."
}

function ConvertTo-SafeName {
    param([Parameter(Mandatory = $true)][string]$Value)

    $safe = $Value -replace '[^A-Za-z0-9._-]', '_'
    $safe = $safe.Trim(' ', '.', '_')
    if ([string]::IsNullOrWhiteSpace($safe)) {
        throw "The value '$Value' cannot be converted to a safe file name."
    }
    return $safe
}

function Write-JsonResult {
    param([Parameter(Mandatory = $true)]$Value)
    $Value | ConvertTo-Json -Depth 12 -Compress
}

function Write-JsonFileAtomic {
    param(
        [Parameter(Mandatory = $true)]$Value,
        [Parameter(Mandatory = $true)][string]$Path,
        [switch]$Replace
    )
    $resolvedPath = [System.IO.Path]::GetFullPath($Path)
    $parent = [System.IO.Path]::GetDirectoryName($resolvedPath)
    [System.IO.Directory]::CreateDirectory($parent) | Out-Null
    if (-not $Replace -and (Test-Path -LiteralPath $resolvedPath)) {
        throw "Refusing to overwrite existing JSON artifact: $resolvedPath"
    }
    $temporary = Join-Path $parent ".$([System.IO.Path]::GetFileName($resolvedPath)).$PID.$([guid]::NewGuid().ToString('N')).tmp"
    try {
        $payload = ($Value | ConvertTo-Json -Depth 12) + "`n"
        [System.IO.File]::WriteAllText(
            $temporary,
            $payload,
            [System.Text.UTF8Encoding]::new($false)
        )
        if ($Replace) {
            [System.IO.File]::Move($temporary, $resolvedPath, $true)
        }
        else {
            [System.IO.File]::Move($temporary, $resolvedPath)
        }
    }
    finally {
        if (Test-Path -LiteralPath $temporary -PathType Leaf) {
            Remove-Item -LiteralPath $temporary
        }
    }
}

function Resolve-PublicBaseUrl {
    param([string]$Value)
    if ([string]::IsNullOrWhiteSpace($Value)) {
        return $null
    }
    $uri = $null
    if (-not [System.Uri]::TryCreate($Value, [System.UriKind]::Absolute, [ref]$uri)) {
        throw 'PublishBaseUrl must be an absolute HTTP(S) URL.'
    }
    if ($uri.Scheme -notin @('http', 'https')) {
        throw 'PublishBaseUrl must use HTTP or HTTPS.'
    }
    if (-not [string]::IsNullOrEmpty($uri.UserInfo) -or
        -not [string]::IsNullOrEmpty($uri.Query) -or
        -not [string]::IsNullOrEmpty($uri.Fragment)) {
        throw 'PublishBaseUrl must not contain userinfo, query parameters, or a fragment.'
    }
    return $uri.AbsoluteUri.TrimEnd('/')
}

function Assert-PublicReceiptSafe {
    param(
        [Parameter(Mandatory = $true)][AllowNull()]$Value,
        [string[]]$PrivateNeedles = @(),
        [string]$Location = '$'
    )
    if ($null -eq $Value) {
        return
    }
    if ($Value -is [string]) {
        $text = [string]$Value
        $hasEmbeddedWindowsPath = [regex]::IsMatch(
            $text,
            '(?i)(?<![A-Za-z0-9+._~-])[a-z]:(?:\\|/(?!/))'
        )
        $hasEmbeddedUncPath = [regex]::IsMatch(
            $text,
            '(?<![\\/])\\\\[^\\/\s]+[\\/]'
        )
        $hasEmbeddedPosixPath = [regex]::IsMatch(
            $text,
            '(?<![/A-Za-z0-9+._~-])/(?!/)[A-Za-z0-9._~-]'
        )
        if ([System.IO.Path]::IsPathRooted($text) -or
            $text.StartsWith('/') -or $text.StartsWith('\') -or
            $hasEmbeddedWindowsPath -or $hasEmbeddedUncPath -or
            $hasEmbeddedPosixPath) {
            throw "Published receipt contains an absolute filesystem path at $Location."
        }
        foreach ($needle in $PrivateNeedles) {
            if (-not [string]::IsNullOrWhiteSpace($needle) -and
                $text.IndexOf($needle, [System.StringComparison]::OrdinalIgnoreCase) -ge 0) {
                throw "Published receipt contains private local identity/path data at $Location."
            }
        }
        return
    }
    if ($Value -is [System.Collections.IDictionary]) {
        foreach ($key in $Value.Keys) {
            Assert-PublicReceiptSafe -Value $Value[$key] -PrivateNeedles $PrivateNeedles -Location "$Location.$key"
        }
        return
    }
    if ($Value -is [System.Collections.IEnumerable]) {
        $index = 0
        foreach ($item in $Value) {
            Assert-PublicReceiptSafe -Value $item -PrivateNeedles $PrivateNeedles -Location "$Location[$index]"
            $index++
        }
    }
}

if ($Action -eq 'Start') {
    if ([string]::IsNullOrWhiteSpace($WindowTitle)) {
        throw 'WindowTitle is required for Action=Start.'
    }
    if ([string]::IsNullOrWhiteSpace($OutputDirectory)) {
        throw 'OutputDirectory is required for Action=Start.'
    }

    $matches = @(Get-Process -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowTitle -eq $WindowTitle })
    if ($matches.Count -ne 1) {
        throw "Expected exactly one visible window with title '$WindowTitle'; found $($matches.Count)."
    }

    $ffmpeg = Resolve-MediaTool -Name 'ffmpeg'
    $safeBaseName = ConvertTo-SafeName -Value $BaseName
    $resolvedOutputDirectory = [System.IO.Path]::GetFullPath($OutputDirectory)
    [System.IO.Directory]::CreateDirectory($resolvedOutputDirectory) | Out-Null

    $runId = [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfffZ')
    $videoPath = Join-Path $resolvedOutputDirectory "$safeBaseName-$runId.mp4"
    $captureStatePath = Join-Path $resolvedOutputDirectory "$safeBaseName-$runId.capture.json"
    if ((Test-Path -LiteralPath $videoPath) -or (Test-Path -LiteralPath $captureStatePath)) {
        throw "Refusing to overwrite an existing capture for run '$runId'."
    }

    $arguments = @(
        '-hide_banner',
        '-loglevel', 'error',
        '-nostdin',
        '-n',
        '-f', 'gdigrab',
        '-draw_mouse', '0',
        '-framerate', $Framerate.ToString([Globalization.CultureInfo]::InvariantCulture),
        '-i', "title=$WindowTitle",
        '-t', $DurationSeconds.ToString([Globalization.CultureInfo]::InvariantCulture),
        '-an',
        '-vf', 'pad=ceil(iw/2)*2:ceil(ih/2)*2',
        '-c:v', 'libx264',
        '-preset', 'veryfast',
        '-crf', '23',
        '-pix_fmt', 'yuv420p',
        '-movflags', '+faststart',
        $videoPath
    )

    $processInfo = [System.Diagnostics.ProcessStartInfo]::new()
    $processInfo.FileName = $ffmpeg
    $processInfo.UseShellExecute = $false
    $processInfo.CreateNoWindow = $true
    foreach ($argument in $arguments) {
        [void]$processInfo.ArgumentList.Add($argument)
    }

    $process = [System.Diagnostics.Process]::Start($processInfo)
    Start-Sleep -Milliseconds 750
    if ($process.HasExited) {
        throw "ffmpeg exited before recording began (exit code $($process.ExitCode))."
    }

    $startedUtc = [DateTime]::UtcNow
    $state = [ordered]@{
        schema_version   = 2
        capture_id       = [guid]::NewGuid().ToString('N')
        status           = 'RECORDING'
        ffmpeg_pid       = $process.Id
        ffmpeg_path      = $ffmpeg
        source_process   = $matches[0].ProcessName
        source_window    = $WindowTitle
        video_path       = $videoPath
        state_path       = $captureStatePath
        started_utc      = $startedUtc.ToString('o')
        expected_end_utc = $startedUtc.AddSeconds($DurationSeconds).ToString('o')
        duration_seconds = $DurationSeconds
        framerate        = $Framerate
    }
    try {
        Write-JsonFileAtomic -Value $state -Path $captureStatePath
    }
    catch {
        $stateFailure = $_
        try {
            if (-not $process.HasExited) {
                $process.Kill($true)
                [void]$process.WaitForExit(5000)
            }
        }
        catch {
            Write-Warning "Could not confirm recorder termination after state-write failure: $($_.Exception.Message)"
        }
        if (Test-Path -LiteralPath $videoPath -PathType Leaf) {
            Remove-Item -LiteralPath $videoPath -Force
        }
        throw (
            "Capture state could not be committed; the current recorder was " +
            "terminated and its partial video removed. $($stateFailure.Exception.Message)"
        )
    }
    Write-JsonResult -Value $state
    exit 0
}

if ([string]::IsNullOrWhiteSpace($StatePath)) {
    throw 'StatePath is required for Action=Complete.'
}
if ([string]::IsNullOrWhiteSpace($IssueId)) {
    throw 'IssueId is required for Action=Complete.'
}
if ([string]::IsNullOrWhiteSpace($Revision)) {
    throw 'Revision is required for Action=Complete.'
}
if ([string]::IsNullOrWhiteSpace($Verdict)) {
    throw 'Verdict is required for Action=Complete.'
}
if ([string]::IsNullOrWhiteSpace($Summary)) {
    throw 'Summary is required for Action=Complete.'
}
if (-not (Test-Path -LiteralPath $StatePath -PathType Leaf)) {
    throw "Capture state file does not exist: $StatePath"
}

$state = Get-Content -Raw -LiteralPath $StatePath | ConvertFrom-Json
if ($state.schema_version -notin @(1, 2) -or $state.status -ne 'RECORDING') {
    throw "Unsupported or already completed capture state: $StatePath"
}

$process = Get-Process -Id ([int]$state.ffmpeg_pid) -ErrorAction SilentlyContinue
if ($process) {
    $expectedEnd = [DateTimeOffset]$state.expected_end_utc
    $remaining = [Math]::Max(0, [Math]::Ceiling(($expectedEnd - [DateTimeOffset]::UtcNow).TotalSeconds))
    $waitMilliseconds = [int](($remaining + 90) * 1000)
    if (-not $process.WaitForExit($waitMilliseconds)) {
        throw "ffmpeg did not finish within the bounded wait for PID $($state.ffmpeg_pid)."
    }
    $process.Refresh()
    $exitCode = $process.ExitCode
    if (($null -ne $exitCode) -and ($exitCode -ne 0)) {
        throw "ffmpeg exited with code $exitCode."
    }
}

$videoPath = [System.IO.Path]::GetFullPath([string]$state.video_path)
if (-not (Test-Path -LiteralPath $videoPath -PathType Leaf)) {
    throw "Recorded video does not exist: $videoPath"
}
$videoFile = Get-Item -LiteralPath $videoPath
if ($videoFile.Length -le 0) {
    throw "Recorded video is empty: $videoPath"
}

$ffprobe = Resolve-MediaTool -Name 'ffprobe'
$probeText = & $ffprobe -v error -show_streams -show_format -of json -- $videoPath
if ($LASTEXITCODE -ne 0) {
    throw "ffprobe could not read the recorded video (exit code $LASTEXITCODE)."
}
$probe = $probeText | ConvertFrom-Json
$videoStream = @($probe.streams | Where-Object { $_.codec_type -eq 'video' }) | Select-Object -First 1
if (-not $videoStream) {
    throw 'The recorded artifact contains no readable video stream.'
}
$duration = [double]::Parse([string]$probe.format.duration, [Globalization.CultureInfo]::InvariantCulture)
if ($duration -lt 3.0) {
    throw "The recorded artifact is too short to be valid evidence ($duration seconds)."
}

$sourceHash = (Get-FileHash -LiteralPath $videoPath -Algorithm SHA256).Hash.ToLowerInvariant()
$safeIssueId = ConvertTo-SafeName -Value $IssueId
$startedUtc = ([DateTimeOffset]$state.started_utc).UtcDateTime
if ($state.schema_version -eq 2) {
    $captureId = [string]$state.capture_id
    if ($captureId -notmatch '^[0-9a-fA-F]{32}$') {
        throw 'Capture state has an invalid capture_id.'
    }
    $captureId = $captureId.ToLowerInvariant()
}
else {
    $identityBytes = [System.Text.Encoding]::UTF8.GetBytes(
        ([System.IO.Path]::GetFullPath($StatePath) + '|' + [string]$state.started_utc + '|' + $sourceHash)
    )
    $identityHasher = [System.Security.Cryptography.SHA256]::Create()
    try {
        $captureId = ([System.BitConverter]::ToString($identityHasher.ComputeHash($identityBytes))).Replace('-', '').ToLowerInvariant().Substring(0, 16)
    }
    finally {
        $identityHasher.Dispose()
    }
}
$runId = $startedUtc.ToString('yyyyMMddTHHmmssfffffffZ') + '-' + $captureId
$finalVideoName = "$safeIssueId-$runId.mp4"
$receiptName = "$safeIssueId-$runId.receipt.json"
$relativeDirectory = Join-Path $safeIssueId $runId
$logicalDirectory = "$safeIssueId/$runId"
$videoArtifactId = "playtest/$logicalDirectory/$finalVideoName"
$receiptArtifactId = "playtest/$logicalDirectory/$receiptName"
$localReceiptPath = Join-Path ([System.IO.Path]::GetDirectoryName($videoPath)) $receiptName
if (Test-Path -LiteralPath $localReceiptPath) {
    throw "Refusing to overwrite an existing playtest receipt: $localReceiptPath"
}
$publicBaseUrl = Resolve-PublicBaseUrl -Value $PublishBaseUrl

$delivery = [ordered]@{
    state         = 'VALIDATED_LOCAL'
    submitted_utc = $null
    base_url      = $publicBaseUrl
    relative_path = $null
    artifact_id   = $videoArtifactId
    receipt_id    = $receiptArtifactId
    blocker       = $null
}

$destinationVideoPath = $null
$destinationReceiptPath = $null
$publishStagingDirectory = $null
$publishFinalDirectory = $null
$publishCommitted = $false
$localReceiptCommitted = $false

try {
    if (-not $SkipPublish -and -not [string]::IsNullOrWhiteSpace($PublishRoot)) {
        if (
            -not [string]::IsNullOrWhiteSpace($PublishProcessName) -and
            -not (Get-Process -Name $PublishProcessName -ErrorAction SilentlyContinue)
        ) {
            $delivery.blocker = "Configured publish process is not running: $PublishProcessName"
        }
        elseif (-not (Test-Path -LiteralPath $PublishRoot -PathType Container)) {
            $delivery.blocker = "Configured publish mount is unavailable: $PublishRoot"
        }
        else {
            $resolvedPublishRoot = [System.IO.Path]::GetFullPath($PublishRoot)
            $publishIssueDirectory = Join-Path $resolvedPublishRoot $safeIssueId
            $publishFinalDirectory = Join-Path $publishIssueDirectory $runId
            if (Test-Path -LiteralPath $publishFinalDirectory) {
                throw "Refusing to overwrite an existing publish run directory: $publishFinalDirectory"
            }
            [System.IO.Directory]::CreateDirectory($publishIssueDirectory) | Out-Null
            $publishStagingDirectory = Join-Path (
                $publishIssueDirectory
            ) ".${runId}.staging-$([guid]::NewGuid().ToString('N'))"
            [System.IO.Directory]::CreateDirectory($publishStagingDirectory) | Out-Null

            $stagedVideoPath = Join-Path $publishStagingDirectory $finalVideoName
            Copy-Item -LiteralPath $videoPath -Destination $stagedVideoPath
            $destinationHash = (Get-FileHash -LiteralPath $stagedVideoPath -Algorithm SHA256).Hash.ToLowerInvariant()
            if ($destinationHash -ne $sourceHash) {
                throw "Publish copy hash mismatch for staged artifact $videoArtifactId"
            }

            $destinationVideoPath = Join-Path $publishFinalDirectory $finalVideoName
            $destinationReceiptPath = Join-Path $publishFinalDirectory $receiptName
            $delivery.state = 'PUBLISHED_TO_MOUNT'
            $delivery.submitted_utc = [DateTime]::UtcNow.ToString('o')
            $delivery.relative_path = "$logicalDirectory/$finalVideoName"
        }
    }

    $receipt = [ordered]@{
        schema_version = 3
        issue_id       = $IssueId
        revision       = $Revision
        verdict        = $Verdict
        summary        = $Summary
        capture        = [ordered]@{
            mode             = 'WINDOW_VIDEO_ONLY'
            started_utc      = $state.started_utc
            duration_seconds = [Math]::Round($duration, 3)
            width            = [int]$videoStream.width
            height           = [int]$videoStream.height
            codec            = [string]$videoStream.codec_name
            pixel_format     = [string]$videoStream.pix_fmt
            framerate        = [string]$videoStream.avg_frame_rate
            bytes            = $videoFile.Length
            sha256           = $sourceHash
            artifact_id      = $videoArtifactId
            filename         = $finalVideoName
            media_type       = 'video/mp4'
        }
        delivery       = $delivery
        completed_utc  = [DateTime]::UtcNow.ToString('o')
    }
    if ($delivery.state -eq 'PUBLISHED_TO_MOUNT') {
        $privateNeedles = @(
            [Environment]::UserName,
            [System.IO.Path]::GetFileName([Environment]::GetFolderPath('UserProfile')),
            [Environment]::GetFolderPath('UserProfile'),
            [System.IO.Path]::GetDirectoryName($videoPath),
            $PublishRoot
        ) | Where-Object { -not [string]::IsNullOrWhiteSpace($_) } | Select-Object -Unique
        Assert-PublicReceiptSafe -Value $receipt -PrivateNeedles $privateNeedles
    }
    Write-JsonFileAtomic -Value $receipt -Path $localReceiptPath
    $localReceiptCommitted = $true

    if ($delivery.state -eq 'PUBLISHED_TO_MOUNT') {
        $stagedReceiptPath = Join-Path $publishStagingDirectory $receiptName
        Copy-Item -LiteralPath $localReceiptPath -Destination $stagedReceiptPath
        [System.IO.Directory]::Move($publishStagingDirectory, $publishFinalDirectory)
        $publishStagingDirectory = $null
        $publishCommitted = $true
    }

    $state.status = 'COMPLETED'
    $state | Add-Member -NotePropertyName completed_utc -NotePropertyValue $receipt.completed_utc -Force
    $state | Add-Member -NotePropertyName receipt_path -NotePropertyValue $localReceiptPath -Force
    $state | Add-Member -NotePropertyName delivery_state -NotePropertyValue $delivery.state -Force
    Write-JsonFileAtomic -Value $state -Path $StatePath -Replace
}
catch {
    $transactionFailure = $_
    if ($null -ne $publishStagingDirectory -and
        (Test-Path -LiteralPath $publishStagingDirectory)) {
        Remove-Item -LiteralPath $publishStagingDirectory -Recurse -Force
    }
    if ($publishCommitted -and $null -ne $publishFinalDirectory -and
        (Test-Path -LiteralPath $publishFinalDirectory)) {
        Remove-Item -LiteralPath $publishFinalDirectory -Recurse -Force
    }
    if ($localReceiptCommitted -and (Test-Path -LiteralPath $localReceiptPath -PathType Leaf)) {
        Remove-Item -LiteralPath $localReceiptPath -Force
    }
    throw $transactionFailure
}

Write-JsonResult -Value ([ordered]@{
    status                = 'COMPLETED'
    verdict               = $Verdict
    delivery_state        = $delivery.state
    video_path            = $videoPath
    receipt_path          = $localReceiptPath
    sha256                = $sourceHash
    duration_seconds      = [Math]::Round($duration, 3)
    width                 = [int]$videoStream.width
    height                = [int]$videoStream.height
    publish_base_url      = $publicBaseUrl
    publish_relative_path = $delivery.relative_path
    publish_video_path    = $destinationVideoPath
    publish_receipt_path  = $destinationReceiptPath
    publish_blocker       = $delivery.blocker
})
