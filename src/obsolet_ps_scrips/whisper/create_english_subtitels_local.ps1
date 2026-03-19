<#
.SYNOPSIS
    Generates English subtitles for all MKV files using Whisper AI (local)
.DESCRIPTION
    Scans a folder recursively for MKV files, checks for English audio and missing subtitles,
    generates English subtitles with Whisper using a local model, and embeds them.
.PARAMETER RootPath
    Root directory to scan (default: E:\converttomkv)
.PARAMETER WhisperExe
    Path to Whisper CLI executable
.PARAMETER WhisperModel
    Path to Whisper model file
.PARAMETER EnhanceMode
    Audio enhancement mode: none, light, full
.PARAMETER KeepTempFiles
    Keep temporary WAV and SRT files
#>

param(
    [string]$RootPath = "E:\converttomkv",
    [string]$WhisperExe = "C:\Program Files\Whisper\whisper-cli.exe",
    [string]$WhisperModel = "C:\Program Files\Whisper\models\ggml-large-v3-turbo-q5_0.bin",
    [ValidateSet("none","light","full")]
    [string]$EnhanceMode = "light",
    [bool]$KeepTempFiles = $false
)

$timestamp = Get-Date -Format "yyyy-MM-dd_HH-mm-ss"
$LogPath = Join-Path $RootPath "SubtitleGeneration_$timestamp.log"

function Write-Log { param([string]$Message); "[$(Get-Date -Format 'HH:mm:ss')] $Message" | Out-File -FilePath $LogPath -Append; Write-Host $Message }

$stats = @{Total=0; Processed=0; Skipped=0; Failed=0}

function Test-PathSafe { param([string]$p) Test-Path -LiteralPath $p -ErrorAction SilentlyContinue }
function Remove-ItemSafe { param([string]$p) if (Test-PathSafe $p) { Remove-Item -LiteralPath $p -Force -ErrorAction SilentlyContinue } }

function Has-EnglishAudio { param([string]$f) ($null -ne (& ffprobe -v error -select_streams a -show_entries stream_tags=language -of csv=p=0 "$f" 2>&1 | Select-String "eng")) }
function Has-EnglishSub { param([string]$f) ($null -ne (& ffprobe -v error -select_streams s -show_entries stream_tags=language -of csv=p=0 "$f" 2>&1 | Select-String "eng")) }

function Get-Duration { param([string]$f) ($d=& ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 "$f" 2>&1) -as [double] }

function Extract-Audio {
    param([string]$Mkv,[string]$Wav,[string]$Mode)
    Write-Log "Extracting audio to WAV..."
    Remove-ItemSafe $Wav
    $filters = switch ($Mode) { "none" { $null } "light" { "dynaudnorm=f=75:g=3:p=0.9" } "full" { "highpass=f=80,lowpass=f=8000,dynaudnorm=f=75:g=3:p=0.9,afftdn=nf=-20" } }
    $args="-y -i `"$Mkv`" -vn -map 0:a:0"
    if ($filters) { $args+=" -af `"$filters`"" }
    $args+=" -ac 1 -ar 16000 -acodec pcm_s16le `"$Wav`""
    Start-Process -FilePath "ffmpeg" -ArgumentList $args -Wait -NoNewWindow
    return (Test-PathSafe $Wav)
}

function Run-Whisper {
    param([string]$Wav,[string]$Exe,[string]$Model)

    $args = @(
        "-m `"$Model`""
        "-l en"
        "-osrt"
        "-f `"$Wav`""
        "--vad"
        "--vad-threshold 0.6"
        "--vad-min-speech-duration-ms 300"
        "--vad-min-silence-duration-ms 200"
        "--beam-size 5"
        "--best-of 5"
        "--temperature 0.2"
        "--no-fallback"
        "--suppress-nst"
    )

    Start-Process -FilePath $Exe -ArgumentList ($args -join " ") -Wait -NoNewWindow

    $srt = "$Wav.srt"
    if (Test-PathSafe $srt) { return $srt } else { return $null }
}




function Adjust-SrtTiming {
    param([string]$Srt,[double]$Scale)
    if ([Math]::Abs($Scale-1.0) -lt 0.01) { return }
    $regex='^(\d{2}:\d{2}:\d{2}),(\d{3}) --> (\d{2}:\d{2}:\d{2}),(\d{3})$'
    $lines=@()
    foreach ($line in Get-Content $Srt) {
        if ($line -match $regex) {
            $start=[TimeSpan]::ParseExact("$($matches[1]).$($matches[2])","hh\:mm\:ss\.fff",$null)
            $end=[TimeSpan]::ParseExact("$($matches[3]).$($matches[4])","hh\:mm\:ss\.fff",$null)
            $lines+="{0:hh\:mm\:ss\,fff} --> {1:hh\:mm\:ss\,fff}" -f ([TimeSpan]::FromTicks([long]($start.Ticks*$Scale))),([TimeSpan]::FromTicks([long]($end.Ticks*$Scale)))
        } else { $lines+=$line }
    }
    $lines | Set-Content -LiteralPath $Srt -Encoding UTF8
}

function Embed-Subtitle {
    param([string]$Mkv,[string]$Srt)

    $mkvmerge = "C:\Program Files\MKVToolNix\mkvmerge.exe"

    $dir  = Split-Path $Mkv
    $base = [System.IO.Path]::GetFileNameWithoutExtension($Mkv)
    $temp = "$dir\$base.fixed.mkv"

    & $mkvmerge -o "$temp" `
        --no-subtitles `
        "$Mkv" `
        --language 0:eng `
        --track-name 0:"English (Whisper Clean)" `
        "$Srt"

    if (Test-PathSafe $temp) {
        Move-Item $temp $Mkv -Force
        return $true
    } else {
        return $false
    }
}

function Clean-Srt {
    param([string]$Srt,[double]$MaxDuration)

    $entries = Get-Content $Srt -Raw -Encoding UTF8
    $blocks = $entries -split "\r?\n\r?\n"

    $clean = @()
    $index = 1

    foreach ($block in $blocks) {

        if ($block -match "(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})") {

            $start = [TimeSpan]::Parse($matches[1].Replace(",",".")) 
            $end   = [TimeSpan]::Parse($matches[2].Replace(",","."))

            if ($end.TotalSeconds -gt $MaxDuration) { continue }
            if (($end - $start).TotalSeconds -gt 15) { continue }

            $text = ($block -split "\r?\n")[2..100] -join " "

            if ($text.Length -lt 3) { continue }
            if ($text -match "^\W+$") { continue }

            $clean += "$index`n$($matches[1]) --> $($matches[2])`n$text`n"
            $index++
        }
    }

    $clean -join "`n" | Set-Content $Srt -Encoding UTF8
}


function Process-Mkv {
    param([System.IO.FileInfo]$File)
    Write-Log "Processing $($File.FullName)"
    if (Has-EnglishSub $File.FullName) { Write-Log "English subtitles exist - skipping"; $stats.Skipped++; return }
    $wav="$($File.DirectoryName)\$($File.BaseName).wav"
    $srt="$wav.srt"
    if (-not (Test-PathSafe $wav)) { if (-not (Extract-Audio $File.FullName $wav $EnhanceMode)) { Write-Log "Audio extraction failed"; $stats.Failed++; return } }
    if (-not (Test-PathSafe $srt)) { $srtPath=Run-Whisper $wav $WhisperExe $WhisperModel; if (-not $srtPath) { Write-Log "Whisper failed"; Remove-ItemSafe $wav; $stats.Failed++; return } }
    $scale=Get-Duration $File.FullName / Get-Duration $wav
    Adjust-SrtTiming $srt $scale
	$videoDuration = Get-Duration $File.FullName
	Clean-Srt $srt $videoDuration
    if (Embed-Subtitle $File.FullName $srt) { Write-Log "Subtitle added"; $stats.Processed++ } else { Write-Log "Embedding failed"; $stats.Failed++ }
    if (-not $KeepTempFiles) { Remove-ItemSafe $wav; Remove-ItemSafe $srt }
}

# Main
$files=Get-ChildItem $RootPath -Recurse -Filter "*.mkv" | Where-Object {$_.BaseName -notmatch "(?i)(trailer|sample|preview)"}
$stats.Total=$files.Count
foreach ($f in $files) { Process-Mkv $f }

Write-Host "Summary: Total=$($stats.Total), Processed=$($stats.Processed), Skipped=$($stats.Skipped), Failed=$($stats.Failed)"
Write-Host "Log: $LogPath"
