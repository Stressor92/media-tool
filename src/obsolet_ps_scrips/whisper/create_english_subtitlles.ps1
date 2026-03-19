<#
.SYNOPSIS
    Generates English subtitles using Whisper AI for MKV files with English audio
.DESCRIPTION
    Scans MKV files, checks for English audio tracks without existing English subtitles,
    extracts audio with optional dialog enhancement, generates subtitles with Whisper, 
    and safely muxes them back into the MKV.
    
    OPTIMIZED FOR NETWORK STORAGE:
    - Processes files locally for speed
    - Automatically copies to temp directory
    - Moves final result back to network
    
    SAFETY: Creates backups, validates all operations, never overwrites without verification.
.PARAMETER RootPath
    Root directory to scan for MKV files (can be network path like Y:\Movies)
.PARAMETER WorkingDir
    Local directory for processing (default: C:\Temp\WhisperWork). 
    Processing locally is MUCH faster than on network storage.
.PARAMETER WhisperExe
    Path to whisper-cli.exe
.PARAMETER WhisperModel
    Path to Whisper model file
.PARAMETER KeepBackups
    Keep .bak backup files after successful processing (default: $false)
.PARAMETER KeepTempFiles
    Keep WAV and SRT files after processing (default: $false)
.PARAMETER EnhanceMode
    Audio enhancement: "none" (fastest), "light" (recommended), "full" (best but slow)
.EXAMPLE
    .\Add-WhisperSubtitles.ps1 -RootPath "Y:\Movies"
.EXAMPLE
    .\Add-WhisperSubtitles.ps1 -RootPath "Y:\Movies" -EnhanceMode "none" -WorkingDir "D:\Temp"
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory=$false)]
    [string]$RootPath = "C:\Users\hille\Downloads\Test",
    
    [Parameter(Mandatory=$false)]
    [string]$WorkingDir = "C:\Temp\WhisperWork",
    
    [Parameter(Mandatory=$false)]
    [bool]$ForceLocalProcessing = $false,
    
    [Parameter(Mandatory=$false)]
    [string]$WhisperExe = "C:\Program Files\Whisper\whisper-cli.exe",
    
    [Parameter(Mandatory=$false)]
    [string]$WhisperModel = "C:\Program Files\Whisper\models\ggml-large-v3-turbo-q5_0.bin",
    
    [Parameter(Mandatory=$false)]
    [bool]$KeepBackups = $false,
    
    [Parameter(Mandatory=$false)]
    [bool]$KeepTempFiles = $false,
    
    [Parameter(Mandatory=$false)]
    [ValidateSet("none", "light", "full")]
    [string]$EnhanceMode = "light",
    
    [Parameter(Mandatory=$false)]
    [string]$LogPath = ""
)

# Configuration
$ffmpeg  = "ffmpeg"
$ffprobe = "ffprobe"

# Initialize log file
if (-not $LogPath) {
    $timestamp = Get-Date -Format "yyyy-MM-dd_HH-mm-ss"
    $LogPath = Join-Path $PSScriptRoot "WhisperSubtitles_$timestamp.log"
}

# Ensure log directory exists
$logDir = Split-Path $LogPath -Parent
if ($logDir -and -not (Test-Path -LiteralPath $logDir)) {
    New-Item -Path $logDir -ItemType Directory -Force | Out-Null
}

# Initialize log file with header
$logHeader = @"
================================================================
Whisper Subtitle Generation Log
================================================================
Script Started: $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")
Root Path: $RootPath
Working Directory: $WorkingDir
Whisper Executable: $WhisperExe
Whisper Model: $WhisperModel
Keep Backups: $KeepBackups
Keep Temp Files: $KeepTempFiles
Enhancement Mode: $EnhanceMode
Log File: $LogPath
================================================================

"@

$logHeader | Out-File -FilePath $LogPath -Encoding UTF8

# Logging function
function Write-Log {
    param(
        [string]$Message,
        [string]$Level = "INFO",
        [ConsoleColor]$Color = "White"
    )
    
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $logMessage = "[$timestamp] [$Level] $Message"
    
    # Write to log file
    $logMessage | Out-File -FilePath $script:LogPath -Append -Encoding UTF8
    
    # Also write to console with color
    Write-Host $Message -ForegroundColor $Color
}

# Statistics
$stats = @{
    Total = 0
    Processed = 0
    Skipped = 0
    Failed = 0
    NoEnglishAudio = 0
    HasEnglishSubs = 0
}

# Detailed tracking for logging
$processedFiles = @()
$skippedFiles = @()
$failedFiles = @()

#region Helper Functions

# Safe file operations using LiteralPath
function Test-PathSafe {
    param([string]$Path)
    Test-Path -LiteralPath $Path -ErrorAction SilentlyContinue
}

function Get-ItemSafe {
    param([string]$Path)
    Get-Item -LiteralPath $Path -ErrorAction SilentlyContinue
}

function Remove-ItemSafe {
    param([string]$Path, [switch]$Force)
    if (Test-PathSafe $Path) {
        Remove-Item -LiteralPath $Path -Force:$Force -ErrorAction SilentlyContinue
    }
}

function Copy-ItemSafe {
    param([string]$Source, [string]$Destination, [switch]$Force)
    Copy-Item -LiteralPath $Source -Destination $Destination -Force:$Force
}

function Move-ItemSafe {
    param([string]$Source, [string]$Destination, [switch]$Force)
    Move-Item -LiteralPath $Source -Destination $Destination -Force:$Force
}

# Verify all required tools are available
function Test-RequiredTools {
    $allGood = $true
    
    # Check FFmpeg
    try {
        $null = & $ffmpeg -version 2>&1
        Write-Log "[OK] FFmpeg found" -Level "INFO" -Color Green
    } catch {
        Write-Log "[ERROR] FFmpeg not found in PATH" -Level "ERROR" -Color Red
        $allGood = $false
    }
    
    # Check FFprobe
    try {
        $null = & $ffprobe -version 2>&1
        Write-Log "[OK] FFprobe found" -Level "INFO" -Color Green
    } catch {
        Write-Log "[ERROR] FFprobe not found in PATH" -Level "ERROR" -Color Red
        $allGood = $false
    }
    
    # Check Whisper
    if (-not (Test-PathSafe $WhisperExe)) {
        Write-Log "[ERROR] Whisper CLI not found at: $WhisperExe" -Level "ERROR" -Color Red
        Write-Log "Download from: https://github.com/ggerganov/whisper.cpp" -Level "INFO" -Color Yellow
        $allGood = $false
    } else {
        Write-Log "[OK] Whisper CLI found" -Level "INFO" -Color Green
    }
    
    # Check Whisper Model
    if (-not (Test-PathSafe $WhisperModel)) {
        Write-Log "[ERROR] Whisper model not found at: $WhisperModel" -Level "ERROR" -Color Red
        $allGood = $false
    } else {
        Write-Log "[OK] Whisper model found" -Level "INFO" -Color Green
    }
    
    return $allGood
}

# Check if MKV has English audio track
function Test-HasEnglishAudio {
    param([string]$MkvPath)
    
    try {
        $result = & $ffprobe -v error -select_streams a `
            -show_entries stream=index:stream_tags=language `
            -of csv=p=0 "$MkvPath" 2>&1
        
        $hasEng = $result | Select-String -Pattern "eng" -Quiet
        return $hasEng
    } catch {
        Write-Warning "Could not check audio streams: $_"
        return $false
    }
}

# Check if MKV already has English subtitles
function Test-HasEnglishSubtitles {
    param([string]$MkvPath)
    
    try {
        $result = & $ffprobe -v error -select_streams s `
            -show_entries stream_tags=language `
            -of csv=p=0 "$MkvPath" 2>&1
        
        $hasEng = $result | Select-String -Pattern "eng" -Quiet
        return $hasEng
    } catch {
        Write-Warning "Could not check subtitle streams: $_"
        return $false
    }
}

# Get duration of media file in seconds
function Get-MediaDuration {
    param([string]$FilePath)
    
    try {
        $durStr = & $ffprobe -v error -show_entries format=duration `
            -of default=nw=1:nk=1 "$FilePath" 2>&1
        
        $duration = $durStr -as [double]
        return $duration
    } catch {
        Write-Warning "Could not get duration for: $FilePath"
        return 0
    }
}

# Extract audio to WAV for Whisper processing with dialog enhancement
function Export-AudioToWav {
    param(
        [string]$MkvPath,
        [string]$WavPath,
        [string]$EnhanceMode = "light"
    )
    
    Write-Host "  Extracting audio to WAV..." -ForegroundColor Cyan
    Write-Host "    From: $MkvPath" -ForegroundColor Gray
    Write-Host "    To:   $WavPath" -ForegroundColor Gray
    
    try {
        # Remove existing WAV if present
        Remove-ItemSafe -Path $WavPath -Force
        
        # Build FFmpeg arguments based on enhancement mode
        $audioFilters = switch ($EnhanceMode) {
            "none" { $null }
            "light" { "dynaudnorm=f=75:g=3:p=0.9" }
            "full" { "highpass=f=80,lowpass=f=8000,dynaudnorm=f=75:g=3:p=0.9,afftdn=nf=-20" }
        }
        
        # Build command arguments
        $ffmpegArgs = "-y -i `"$MkvPath`" -vn -map 0:a:0"
        
        if ($audioFilters) {
            $ffmpegArgs += " -af `"$audioFilters`""
            Write-Host "    Audio enhancement: $EnhanceMode mode" -ForegroundColor Cyan
            Write-Log "    Audio filters ($EnhanceMode): $audioFilters" -Level "INFO"
        } else {
            Write-Host "    Audio enhancement: DISABLED (raw audio - fastest)" -ForegroundColor Cyan
            Write-Log "    Audio filters: none (raw extraction)" -Level "INFO"
        }
        
        $ffmpegArgs += " -ac 1 -ar 16000 -acodec pcm_s16le `"$WavPath`""
        
        # Use Start-Process to ensure synchronous execution
        $processInfo = New-Object System.Diagnostics.ProcessStartInfo
        $processInfo.FileName = "ffmpeg"
        $processInfo.Arguments = $ffmpegArgs
        $processInfo.RedirectStandardError = $true
        $processInfo.RedirectStandardOutput = $true
        $processInfo.UseShellExecute = $false
        $processInfo.CreateNoWindow = $true
        
        $process = New-Object System.Diagnostics.Process
        $process.StartInfo = $processInfo
        
        Write-Host "    Starting FFmpeg extraction..." -ForegroundColor Gray
        $startTime = Get-Date
        $process.Start() | Out-Null
        
        # Read output to prevent blocking
        $stdout = $process.StandardOutput.ReadToEndAsync()
        $stderr = $process.StandardError.ReadToEndAsync()
        
        # Wait for completion
        $process.WaitForExit()
        $exitCode = $process.ExitCode
        $elapsed = (Get-Date) - $startTime
        
        Write-Host "    FFmpeg completed (exit code: $exitCode, time: $([math]::Round($elapsed.TotalSeconds, 1))s)" -ForegroundColor Gray
        
        # Wait for filesystem sync
        Write-Host "    Waiting for filesystem to sync..." -ForegroundColor Gray
        Start-Sleep -Milliseconds 3000
        
        # Check if WAV was created with retry logic
        $maxRetries = 5
        $retryCount = 0
        $wavExists = $false
        
        while ($retryCount -lt $maxRetries -and -not $wavExists) {
            if (Test-PathSafe -LiteralPath $WavPath) {
                $wavExists = $true
            } else {
                $retryCount++
                Write-Host "    Retry $retryCount/$maxRetries - checking for WAV file..." -ForegroundColor Yellow
                Start-Sleep -Seconds 2
            }
        }
        
        if ($wavExists) {
            $size = (Get-ItemSafe -LiteralPath $WavPath).Length
            Write-Host "    WAV file found: $([math]::Round($size/1MB, 2)) MB" -ForegroundColor Gray
            
            if ($size -gt 100KB) {
                Write-Host "  [OK] WAV extracted: $([math]::Round($size/1MB, 2)) MB" -ForegroundColor Green
                return $true
            } else {
                Write-Warning "  [ERROR] WAV file too small ($([math]::Round($size/1KB, 2)) KB) - likely corrupted"
                Remove-ItemSafe -LiteralPath $WavPath -Force
                return $false
            }
        } else {
            Write-Warning "  [ERROR] WAV file was not created (exit code: $exitCode)"
            Write-Warning "    Expected path: $WavPath"
            return $false
        }
    } catch {
        Write-Error "  [ERROR] Exception during WAV extraction: $_"
        return $false
    }
}

# Run Whisper to generate subtitles
function Invoke-WhisperTranscription {
    param(
        [string]$WavPath,
        [string]$WhisperExePath,
        [string]$ModelPath
    )
    
    Write-Host "  Running Whisper AI transcription (this may take 20-40 minutes for a 2-hour movie)..." -ForegroundColor Cyan
    Write-Log "  Starting Whisper transcription on: $WavPath" -Level "INFO"
    
    try {
        $whisperArgs = @(
            "-m", "`"$ModelPath`""
            "-l", "en"
            "-osrt"
            "-f", "`"$WavPath`""
        )
        
        $argsString = $whisperArgs -join " "
        
        Write-Host "    Whisper command: $WhisperExePath $argsString" -ForegroundColor Gray
        Write-Log "    Whisper command: $WhisperExePath $argsString" -Level "INFO"
        
        Write-Host "  ╔════════════════════════════════════════════════════════════════╗" -ForegroundColor Yellow
        Write-Host "  ║ WHISPER OUTPUT (Live) - Watch for hallucination loops!         ║" -ForegroundColor Yellow
        Write-Host "  ║ Press Ctrl+C if you see repeating text or nonsense             ║" -ForegroundColor Yellow
        Write-Host "  ╚════════════════════════════════════════════════════════════════╝" -ForegroundColor Yellow
        Write-Host ""
        Write-Host "  Started at: $(Get-Date -Format 'HH:mm:ss')" -ForegroundColor Gray
        Write-Host "  ────────────────────────────────────────────────────────────────" -ForegroundColor DarkGray
        Write-Host ""
        
        # Execute Whisper with LIVE output
        $processInfo = New-Object System.Diagnostics.ProcessStartInfo
        $processInfo.FileName = $WhisperExePath
        $processInfo.Arguments = $argsString
        $processInfo.RedirectStandardError = $false  # Show stderr live
        $processInfo.RedirectStandardOutput = $false  # Show stdout live
        $processInfo.UseShellExecute = $false
        $processInfo.CreateNoWindow = $false  # Show console window
        $processInfo.WorkingDirectory = Split-Path $WavPath
        
        $process = New-Object System.Diagnostics.Process
        $process.StartInfo = $processInfo
        
        $startTime = Get-Date
        $process.Start() | Out-Null
        
        # Wait for completion with periodic status updates
        $lastUpdate = Get-Date
        $updateInterval = 60  # Update every 60 seconds
        
        while (-not $process.HasExited) {
            Start-Sleep -Seconds 10
            
            $elapsed = (Get-Date) - $startTime
            $now = Get-Date
            
            # Show elapsed time periodically
            if (($now - $lastUpdate).TotalSeconds -ge $updateInterval) {
                Write-Host ""
                Write-Host "  [STATUS] Elapsed: $([math]::Floor($elapsed.TotalMinutes)) min $($elapsed.Seconds) sec" -ForegroundColor Cyan
                $lastUpdate = $now
            }
            
            # Safety check: if running for more than 2 hours, something might be wrong
            if ($elapsed.TotalHours -gt 2) {
                Write-Host ""
                Write-Warning "   WARNING: Whisper has been running for over 2 hours!"
                Write-Warning "  This might indicate a hallucination loop or other problem."
                Write-Warning "  Press Ctrl+C to cancel if you see repeating text above."
                Write-Host ""
            }
        }
        
        $process.WaitForExit()
        $exitCode = $process.ExitCode
        $totalTime = (Get-Date) - $startTime
        
        Write-Host ""
        Write-Host "  ────────────────────────────────────────────────────────────────" -ForegroundColor DarkGray
        Write-Host "  ✓ Whisper completed!" -ForegroundColor Green
        Write-Host "  Total time: $([math]::Floor($totalTime.TotalMinutes)) min $($totalTime.Seconds) sec" -ForegroundColor Green
        Write-Host "  Exit code: $exitCode" -ForegroundColor Gray
        Write-Host ""
        
        Write-Log "    Whisper exit code: $exitCode, duration: $([math]::Round($totalTime.TotalMinutes, 1)) minutes" -Level "INFO"
        
        $srtPath = "$WavPath.srt"
        
        # Wait a moment for file to be written
        Start-Sleep -Seconds 2
        
        if (Test-PathSafe $srtPath) {
            $srtSize = (Get-ItemSafe $srtPath).Length
            Write-Host "  [OK] SRT file created: $([math]::Round($srtSize/1KB, 2)) KB" -ForegroundColor Green
            
            # Check for potential hallucination by looking at file size
            # A 2-hour movie should produce roughly 50-200 KB of subtitles
            # If it's much larger, might be hallucination
            $wavSize = (Get-ItemSafe $WavPath).Length
            $expectedSrtSize = ($wavSize / 1MB) * 0.5  # Rough estimate: 0.5 KB per MB of WAV
            
            if ($srtSize -gt ($expectedSrtSize * 10)) {
                Write-Warning "  SRT file is unusually large ($([math]::Round($srtSize/1KB, 2)) KB)"
                Write-Warning "  This might indicate hallucination. Please check the SRT file contents."
            }
            
            Write-Log "    SRT file created: $srtSize bytes" -Level "INFO"
            return $srtPath
        } else {
            Write-Warning "  [ERROR] Whisper did not create SRT file"
            return $null
        }
    } catch {
        Write-Error "  [ERROR] Whisper execution failed: $_"
        Write-Log "  Whisper execution exception: $_" -Level "ERROR"
        return $null
    }
}

# Scale SRT timing to match actual movie duration
function Repair-SrtTiming {
    param(
        [string]$SrtFile,
        [double]$ScaleFactor
    )
    
    if ($ScaleFactor -eq 0 -or [Math]::Abs($ScaleFactor - 1.0) -lt 0.01) {
        Write-Host "  [INFO] No timing adjustment needed (factor: $ScaleFactor)" -ForegroundColor Yellow
        return $true
    }
    
    Write-Host "  Adjusting SRT timing (scale factor: $([math]::Round($ScaleFactor, 4)))..." -ForegroundColor Cyan
    
    try {
        # Create backup
        $backupFile = "$SrtFile.original"
        Copy-ItemSafe -Source $SrtFile -Destination $backupFile -Force
        
        # SRT timestamp regex
        $regex = '^(\d{2}:\d{2}:\d{2}),(\d{3}) --> (\d{2}:\d{2}:\d{2}),(\d{3})$'
        $outputLines = @()
        
        foreach ($line in Get-Content -LiteralPath $SrtFile -Encoding UTF8) {
            if ($line -match $regex) {
                # Parse start time
                $startTime = [TimeSpan]::ParseExact(
                    "$($matches[1]).$($matches[2])", 
                    "hh\:mm\:ss\.fff", 
                    $null
                )
                
                # Parse end time
                $endTime = [TimeSpan]::ParseExact(
                    "$($matches[3]).$($matches[4])", 
                    "hh\:mm\:ss\.fff", 
                    $null
                )
                
                # Scale times
                $scaledStart = [TimeSpan]::FromTicks([long]($startTime.Ticks * $ScaleFactor))
                $scaledEnd = [TimeSpan]::FromTicks([long]($endTime.Ticks * $ScaleFactor))
                
                # Format back to SRT format (with comma, not period)
                $newLine = "{0:hh\:mm\:ss\,fff} --> {1:hh\:mm\:ss\,fff}" -f $scaledStart, $scaledEnd
                $outputLines += $newLine
            } else {
                $outputLines += $line
            }
        }
        
        # Write adjusted SRT
        $outputLines | Set-Content -LiteralPath $SrtFile -Encoding UTF8
        Write-Host "  [OK] SRT timing adjusted" -ForegroundColor Green
        
        # Clean up backup if not keeping
        if (-not $script:KeepBackups) {
            Remove-ItemSafe -Path $backupFile -Force
        }
        
        return $true
    } catch {
        Write-Error "  [ERROR] Failed to adjust SRT timing: $_"
        return $false
    }
}

# Post-process SRT file for better readability
function Optimize-SrtReadability {
    param([string]$SrtFile)
    
    Write-Host "  Optimizing SRT for readability..." -ForegroundColor Cyan
    Write-Log "    Post-processing SRT: $SrtFile" -Level "INFO"
    
    try {
        $content = Get-Content -LiteralPath $SrtFile -Encoding UTF8 -Raw
        
        $beforeLines = ($content -split "`n").Count
        
        # Remove excessive blank lines
        $content = $content -replace "(`r?`n){3,}", "`r`n`r`n"
        
        # Ensure proper spacing
        $content = $content -replace "(`r?`n)(\d{2}:\d{2}:\d{2})", "`r`n`r`n`$2"
        
        # Remove trailing whitespace
        $lines = $content -split "`r?`n"
        $lines = $lines | ForEach-Object { $_.TrimEnd() }
        
        # Save optimized version
        $lines | Set-Content -LiteralPath $SrtFile -Encoding UTF8
        
        $afterLines = $lines.Count
        Write-Host "    Cleaned SRT: $beforeLines -> $afterLines lines" -ForegroundColor Gray
        Write-Log "    SRT optimization complete: $beforeLines -> $afterLines lines" -Level "INFO"
        
        return $true
    } catch {
        Write-Warning "  [WARNING] Could not optimize SRT: $_"
        Write-Log "    SRT optimization failed: $_" -Level "WARN"
        return $false
    }
}

# Safely mux SRT into MKV
function Add-SubtitleToMkv {
    param(
        [string]$MkvPath,
        [string]$SrtPath
    )
    
    Write-Host "  Muxing subtitle into MKV..." -ForegroundColor Cyan
    
    try {
        $dir = Split-Path $MkvPath
        $baseName = [System.IO.Path]::GetFileNameWithoutExtension($MkvPath)
        
        # Create temporary output file
        $tempMkv = Join-Path $dir "$baseName.temp.mkv"
        
        # CRITICAL: Create backup of original MKV
        $backupMkv = "$MkvPath.backup"
        Write-Host "  [SAFETY] Creating backup: $([System.IO.Path]::GetFileName($backupMkv))" -ForegroundColor Yellow
        Copy-ItemSafe -Source $MkvPath -Destination $backupMkv -Force
        
        # Mux: copy all streams from MKV, add SRT as new subtitle stream
        & $ffmpeg -y `
            -i "$MkvPath" `
            -i "$SrtPath" `
            -map 0 `
            -map 1 `
            -c copy `
            -metadata:s:s:0 language=eng `
            -metadata:s:s:0 title="English (Whisper AI)" `
            "$tempMkv" 2>&1 | Out-Null
        
        # Verify temp file was created and has reasonable size
        if (Test-PathSafe $tempMkv) {
            $originalSize = (Get-ItemSafe $MkvPath).Length
            $tempSize = (Get-ItemSafe $tempMkv).Length
            
            # Temp file should be similar size (allow 10% variance)
            $sizeRatio = $tempSize / $originalSize
            
            if ($sizeRatio -ge 0.9 -and $sizeRatio -le 1.1) {
                # Replace original with temp
                Move-ItemSafe -Source $tempMkv -Destination $MkvPath -Force
                Write-Host "  [OK] Subtitle successfully added to MKV" -ForegroundColor Green
                Write-Host "      Original: $([math]::Round($originalSize/1MB, 2)) MB" -ForegroundColor Gray
                Write-Host "      New:      $([math]::Round($tempSize/1MB, 2)) MB" -ForegroundColor Gray
                
                # Remove backup if not keeping
                if (-not $script:KeepBackups) {
                    Remove-ItemSafe -Path $backupMkv -Force
                } else {
                    Write-Host "  [INFO] Backup kept: $([System.IO.Path]::GetFileName($backupMkv))" -ForegroundColor Yellow
                }
                
                return $true
            } else {
                Write-Warning "  [ERROR] Output file size suspicious (ratio: $([math]::Round($sizeRatio, 2)))"
                Write-Warning "  Original: $([math]::Round($originalSize/1MB, 2)) MB"
                Write-Warning "  New: $([math]::Round($tempSize/1MB, 2)) MB"
                Write-Host "  [SAFETY] Restoring from backup" -ForegroundColor Yellow
                
                Remove-ItemSafe -Path $tempMkv -Force
                return $false
            }
        } else {
            Write-Warning "  [ERROR] Muxing failed - temp file not created"
            Remove-ItemSafe -Path $backupMkv -Force
            return $false
        }
    } catch {
        Write-Error "  [ERROR] Exception during muxing: $_"
        return $false
    }
}

# Clean up temporary files
function Remove-TempFiles {
    param(
        [string]$WavPath,
        [string]$SrtPath
    )
    
    if (-not $script:KeepTempFiles) {
        Write-Host "  Cleaning up temporary files..." -ForegroundColor Cyan
        
        Remove-ItemSafe -Path $WavPath -Force
        Remove-ItemSafe -Path $SrtPath -Force
        Remove-ItemSafe -Path "$SrtPath.original" -Force
        
        Write-Host "  [OK] Temporary files removed" -ForegroundColor Green
    } else {
        Write-Host "  [INFO] Temporary files kept (WAV, SRT)" -ForegroundColor Yellow
    }
}

#endregion

#region Main Processing

# Main function to process a single MKV file
function Process-MkvFile {
    param([System.IO.FileInfo]$File)
    
    $mkvPath = $File.FullName
    $baseName = $File.BaseName
    $dir = $File.DirectoryName
    
    $separator = "`n================================================="
    Write-Host $separator -ForegroundColor Cyan
    Write-Host "Processing: $($File.Name)" -ForegroundColor Cyan
    Write-Host $separator -ForegroundColor Cyan
    
    Write-Log "$separator
Processing: $mkvPath
$separator" -Level "INFO"
    
    # Check for English audio
    Write-Host "Checking for English audio track..." -ForegroundColor Cyan
    if (-not (Test-HasEnglishAudio -MkvPath $mkvPath)) {
        $msg = "[SKIP] No English audio track found"
        Write-Host $msg -ForegroundColor Yellow
        Write-Log "$mkvPath - $msg" -Level "SKIP"
        $script:stats.NoEnglishAudio++
        $script:skippedFiles += @{File = $mkvPath; Reason = "No English audio"}
        return
    }
    Write-Host "[OK] English audio track found" -ForegroundColor Green
    Write-Log "$mkvPath - English audio track found" -Level "INFO"
    
    # Check for existing English subtitles
    Write-Host "Checking for existing English subtitles..." -ForegroundColor Cyan
    if (Test-HasEnglishSubtitles -MkvPath $mkvPath) {
        $msg = "[SKIP] English subtitles already exist"
        Write-Host $msg -ForegroundColor Yellow
        Write-Log "$mkvPath - $msg" -Level "SKIP"
        $script:stats.HasEnglishSubs++
        $script:skippedFiles += @{File = $mkvPath; Reason = "English subtitles already exist"}
        return
    }
    Write-Host "[OK] No English subtitles found - will generate" -ForegroundColor Green
    Write-Log "$mkvPath - No English subtitles found, will generate" -Level "INFO"
    
    # Determine if we need local processing
    # Criteria: Network path (Y:\, \\server\) OR ForceLocalProcessing enabled
    $isNetworkPath = $mkvPath -match "^\\\\|^[A-Z]:" -and -not ($mkvPath -match "^C:")
    $useLocalProcessing = ($isNetworkPath -or $script:ForceLocalProcessing) -and $script:WorkingDir
    
    if ($useLocalProcessing) {
        if ($isNetworkPath) {
            Write-Host "Network file detected - using local working directory for speed" -ForegroundColor Yellow
        } else {
            Write-Host "ForceLocalProcessing enabled - using working directory" -ForegroundColor Yellow
        }
        Write-Log "  Using local processing: $script:WorkingDir" -Level "INFO"
        
        # Create working directory if needed
        if (-not (Test-PathSafe $script:WorkingDir)) {
            New-Item -Path $script:WorkingDir -ItemType Directory -Force | Out-Null
        }
        
        # Copy MKV to local temp (if not already there)
        $localMkvName = [System.IO.Path]::GetFileName($mkvPath)
        $localMkvPath = Join-Path $script:WorkingDir $localMkvName
        
        # Only copy if source != destination
        if ($mkvPath -ne $localMkvPath) {
            Write-Host "  Copying MKV to working directory..." -ForegroundColor Cyan
            $copyStart = Get-Date
            Copy-ItemSafe -Source $mkvPath -Destination $localMkvPath -Force
            $copyTime = (Get-Date) - $copyStart
            Write-Host "  [OK] Copy completed in $([math]::Round($copyTime.TotalSeconds, 1))s" -ForegroundColor Green
            $needsCopyBack = $true
        } else {
            Write-Host "  File already in working directory" -ForegroundColor Gray
            $needsCopyBack = $false
        }
        
        # ALL processing happens locally - including WAV
        $localBaseName = [System.IO.Path]::GetFileNameWithoutExtension($localMkvName)
        $localWavPath = Join-Path $script:WorkingDir "$localBaseName.wav"
        $localSrtPath = "$localWavPath.srt"
        
        $processingPath = $localMkvPath
        $wavPath = $localWavPath  # WAV created locally!
        $srtPath = $localSrtPath  # SRT created locally!
    } else {
        # Local file - process in place
        $processingPath = $mkvPath
        $wavPath = Join-Path $dir "$baseName.wav"
        $srtPath = "$wavPath.srt"
        $needsCopyBack = $false
    }
    
    Write-Host "  Processing path: $processingPath" -ForegroundColor Gray
    Write-Host "  WAV path: $wavPath" -ForegroundColor Gray
    Write-Log "  WAV path: $wavPath" -Level "INFO"
    
    # Step 1: Extract audio to WAV
    if (Test-PathSafe $wavPath) {
        $existingSize = (Get-ItemSafe $wavPath).Length
        $msg = "[INFO] WAV file already exists ($([math]::Round($existingSize/1MB, 2)) MB), skipping extraction"
        Write-Host "  $msg" -ForegroundColor Yellow
        Write-Log "  $mkvPath - $msg" -Level "INFO"
    } else {
        if (-not (Export-AudioToWav -MkvPath $processingPath -WavPath $wavPath -EnhanceMode $script:EnhanceMode)) {
            $errorMsg = "[FAILED] Could not extract audio"
            Write-Error $errorMsg
            Write-Log "$mkvPath - $errorMsg" -Level "ERROR"
            
            # Clean up local copy if exists
            if ($needsCopyBack) {
                Remove-ItemSafe -Path $localMkvPath -Force
            }
            
            $script:stats.Failed++
            $script:failedFiles += @{File = $mkvPath; Error = "Audio extraction failed"}
            return
        }
        Write-Log "  $mkvPath - WAV extracted successfully" -Level "INFO"
    }
    
    # Verify WAV duration matches movie duration
    Write-Host "  Verifying audio duration..." -ForegroundColor Cyan
    $movieDuration = Get-MediaDuration -FilePath $processingPath
    $wavDuration = Get-MediaDuration -FilePath $wavPath
    
    if ($movieDuration -gt 0 -and $wavDuration -gt 0) {
        $durationDiff = [Math]::Abs($movieDuration - $wavDuration)
        $diffPercent = ($durationDiff / $movieDuration) * 100
        
        Write-Host "    Movie duration: $([math]::Round($movieDuration, 2)) seconds" -ForegroundColor Gray
        Write-Host "    WAV duration:   $([math]::Round($wavDuration, 2)) seconds" -ForegroundColor Gray
        Write-Host "    Difference:     $([math]::Round($durationDiff, 2)) seconds ($([math]::Round($diffPercent, 2))%)" -ForegroundColor Gray
        
        if ($diffPercent -gt 5) {
            Write-Warning "  [WARNING] Significant duration mismatch ($([math]::Round($diffPercent, 2))%)"
            Write-Warning "  Subtitles may require timing adjustment after Whisper"
        } else {
            Write-Host "  [OK] Duration match is good" -ForegroundColor Green
        }
    } else {
        Write-Warning "  [WARNING] Could not verify durations"
    }
    
    # Step 2: Run Whisper transcription
    if (-not (Test-PathSafe $srtPath)) {
        $generatedSrt = Invoke-WhisperTranscription `
            -WavPath $wavPath `
            -WhisperExePath $WhisperExe `
            -ModelPath $WhisperModel
        
        if (-not $generatedSrt) {
            $errorMsg = "[FAILED] Whisper transcription failed"
            Write-Error $errorMsg
            Write-Log "$mkvPath - $errorMsg" -Level "ERROR"
            Remove-TempFiles -WavPath $wavPath -SrtPath $srtPath
            
            # Clean up local copy if exists
            if ($needsCopyBack) {
                Remove-ItemSafe -Path $localMkvPath -Force
            }
            
            $script:stats.Failed++
            $script:failedFiles += @{File = $mkvPath; Error = "Whisper transcription failed"}
            return
        }
        Write-Log "  $mkvPath - Whisper transcription completed" -Level "INFO"
    } else {
        $msg = "[INFO] SRT file already exists, skipping transcription"
        Write-Host "  $msg" -ForegroundColor Yellow
        Write-Log "  $mkvPath - $msg" -Level "INFO"
    }
    
    # Step 3: Adjust SRT timing
    Write-Host "Checking timing synchronization..." -ForegroundColor Cyan
    $movieDuration = Get-MediaDuration -FilePath $processingPath
    $wavDuration = Get-MediaDuration -FilePath $wavPath
    
    if ($movieDuration -gt 0 -and $wavDuration -gt 0) {
        $scaleFactor = $movieDuration / $wavDuration
        Write-Host "  Movie duration: $([math]::Round($movieDuration, 2)) seconds" -ForegroundColor Cyan
        Write-Host "  WAV duration: $([math]::Round($wavDuration, 2)) seconds" -ForegroundColor Cyan
        Write-Log "  $mkvPath - Duration check: Movie=$([math]::Round($movieDuration, 2))s, WAV=$([math]::Round($wavDuration, 2))s, Scale=$([math]::Round($scaleFactor, 4))" -Level "INFO"
        
        if (-not (Repair-SrtTiming -SrtFile $srtPath -ScaleFactor $scaleFactor)) {
            Write-Warning "[WARNING] Could not adjust SRT timing, proceeding anyway"
            Write-Log "  $mkvPath - WARNING: Could not adjust SRT timing" -Level "WARN"
        }
    } else {
        Write-Warning "[WARNING] Could not determine durations for timing adjustment"
        Write-Log "  $mkvPath - WARNING: Could not determine durations" -Level "WARN"
    }
    
    # Step 3.5: Optimize SRT readability
    Optimize-SrtReadability -SrtFile $srtPath | Out-Null
    
    # Step 4: Mux subtitle into MKV
    if (Add-SubtitleToMkv -MkvPath $processingPath -SrtPath $srtPath) {
        $successMsg = "[SUCCESS] Subtitles added successfully!"
        Write-Host "`n$successMsg" -ForegroundColor Green
        Write-Log "$mkvPath - $successMsg" -Level "SUCCESS"
        
        # If we processed locally, copy back to original location
        if ($needsCopyBack) {
            Write-Host "  Copying processed MKV back to original location..." -ForegroundColor Cyan
            $copyStart = Get-Date
            Copy-ItemSafe -Source $localMkvPath -Destination $mkvPath -Force
            $copyTime = (Get-Date) - $copyStart
            Write-Host "  [OK] Copy back completed in $([math]::Round($copyTime.TotalSeconds, 1))s" -ForegroundColor Green
            
            # Clean up local files
            Remove-ItemSafe -Path $localMkvPath -Force
        }
        
        $script:stats.Processed++
        $script:processedFiles += $mkvPath
        
        # Clean up temp files
        Remove-TempFiles -WavPath $wavPath -SrtPath $srtPath
    } else {
        $errorMsg = "[FAILED] Could not add subtitles to MKV"
        Write-Error "`n$errorMsg"
        Write-Log "$mkvPath - $errorMsg" -Level "ERROR"
        Write-Host "Temporary files kept for inspection" -ForegroundColor Yellow
        Write-Log "  $mkvPath - Temporary files kept for inspection" -Level "INFO"
        
        # Clean up local copy if exists
        if ($needsCopyBack) {
            Remove-ItemSafe -Path $localMkvPath -Force
        }
        
        $script:stats.Failed++
        $script:failedFiles += @{File = $mkvPath; Error = "Failed to mux subtitles into MKV"}
    }
}

#endregion

#region Script Execution

# Header
Write-Host "=======================================================" -ForegroundColor Cyan
Write-Host "  Whisper Subtitle Generator for MKV Files" -ForegroundColor Cyan
Write-Host "=======================================================" -ForegroundColor Cyan
Write-Host ""

# Verify tools
Write-Host "Verifying required tools..." -ForegroundColor Cyan
if (-not (Test-RequiredTools)) {
    Write-Error "Required tools missing. Please install and try again."
    exit 1
}
Write-Host ""

# Verify root path
if (-not (Test-PathSafe $RootPath)) {
    Write-Error "Root path does not exist: $RootPath"
    exit 1
}

# Create working directory if needed
if ($WorkingDir -and -not (Test-PathSafe $WorkingDir)) {
    Write-Host "Creating working directory: $WorkingDir" -ForegroundColor Cyan
    New-Item -Path $WorkingDir -ItemType Directory -Force | Out-Null
}

# Display configuration
Write-Host "Configuration:" -ForegroundColor Cyan
Write-Host "  Root Path: $RootPath"
Write-Host "  Working Directory: $WorkingDir"
Write-Host "  Force Local Processing: $ForceLocalProcessing"
Write-Host "  Whisper Executable: $WhisperExe"
Write-Host "  Whisper Model: $WhisperModel"
Write-Host "  Keep Backups: $KeepBackups"
Write-Host "  Keep Temp Files: $KeepTempFiles"
Write-Host "  Enhancement Mode: $EnhanceMode (none=fastest, light=recommended, full=best quality but slow)"
Write-Host ""

# Scan for MKV files
Write-Host "Scanning for MKV files..." -ForegroundColor Cyan
$files = Get-ChildItem -LiteralPath $RootPath -Recurse -File | Where-Object {
    $_.Extension -eq ".mkv" -and
    ($_.BaseName -notmatch "(?i)(trailer|sample|preview)")
}

$stats.Total = $files.Count

if ($stats.Total -eq 0) {
    Write-Host "No MKV files found." -ForegroundColor Yellow
    exit 0
}

Write-Host "Found $($stats.Total) MKV file(s) to check`n" -ForegroundColor Green

# Process each file
$fileNumber = 0
foreach ($file in $files) {
    $fileNumber++
    Write-Host "`n" -NoNewline
    Write-Host "═══════════════════════════════════════════════════════" -ForegroundColor Magenta
    Write-Host " FILE $fileNumber of $($stats.Total)" -ForegroundColor Magenta
    Write-Host "═══════════════════════════════════════════════════════" -ForegroundColor Magenta
    
    Process-MkvFile -File $file
    $stats.Skipped = $stats.NoEnglishAudio + $stats.HasEnglishSubs
    
    # Show running statistics
    if ($fileNumber -lt $stats.Total) {
        Write-Host "`n--- Progress: $fileNumber/$($stats.Total) files processed ---" -ForegroundColor Cyan
        Write-Host "  Completed: $($stats.Processed) | Skipped: $($stats.Skipped) | Failed: $($stats.Failed)" -ForegroundColor Gray
    }
}

# Summary
$summaryHeader = @"

=======================================================
  Processing Summary
=======================================================
"@

Write-Host $summaryHeader -ForegroundColor Cyan
Write-Log $summaryHeader -Level "INFO"

$summaryStats = @"
Total files scanned:        $($stats.Total)
Successfully processed:     $($stats.Processed)
Skipped (no English audio): $($stats.NoEnglishAudio)
Skipped (has English subs): $($stats.HasEnglishSubs)
Failed:                     $($stats.Failed)
"@

Write-Host "  Total files scanned:       $($stats.Total)"
Write-Host "  Successfully processed:    $($stats.Processed)" -ForegroundColor Green
Write-Host "  Skipped (no English audio): $($stats.NoEnglishAudio)" -ForegroundColor Yellow
Write-Host "  Skipped (has English subs): $($stats.HasEnglishSubs)" -ForegroundColor Yellow
Write-Host "  Failed:                    $($stats.Failed)" -ForegroundColor $(if ($stats.Failed -gt 0) { "Red" } else { "White" })
Write-Host "=======================================================" -ForegroundColor Cyan

Write-Log $summaryStats -Level "SUMMARY"

# Detailed file lists in log
$detailedLog = @"

=======================================================
DETAILED FILE REPORT
=======================================================

"@

if ($processedFiles.Count -gt 0) {
    $detailedLog += "SUCCESSFULLY PROCESSED FILES ($($processedFiles.Count)):
"
    $processedFiles | ForEach-Object {
        $detailedLog += "  [OK] $_
"
    }
    $detailedLog += "
"
}

if ($skippedFiles.Count -gt 0) {
    $detailedLog += "SKIPPED FILES ($($skippedFiles.Count)):
"
    $skippedFiles | ForEach-Object {
        $detailedLog += "  [SKIP] $($_.File) - Reason: $($_.Reason)
"
    }
    $detailedLog += "
"
}

if ($failedFiles.Count -gt 0) {
    $detailedLog += "FAILED FILES ($($failedFiles.Count)):
"
    $failedFiles | ForEach-Object {
        $detailedLog += "  [FAIL] $($_.File) - Error: $($_.Error)
"
    }
    $detailedLog += "
"
}

$detailedLog += @"
=======================================================
VERIFICATION CHECKLIST
=======================================================

Please verify the following for each processed file:
1. Check that English subtitles appear in video player
2. Verify subtitle timing is synchronized
3. Confirm original MKV file was not corrupted
4. Check that WAV and SRT temp files were cleaned up (unless -KeepTempFiles was used)
5. Verify backup files (.backup) were removed (unless -KeepBackups was used)

Directories processed:
"@

# List all unique directories
$directories = $files | ForEach-Object { $_.DirectoryName } | Select-Object -Unique | Sort-Object
$directories | ForEach-Object {
    $dirFiles = $files | Where-Object { $_.DirectoryName -eq $_ }
    $detailedLog += "
  $_ ($($dirFiles.Count) file(s))"
}

$detailedLog += @"


=======================================================
Script completed: $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")
=======================================================
"@

# Write detailed log to file
$detailedLog | Out-File -FilePath $LogPath -Append -Encoding UTF8

# Show log file location
Write-Host ""
Write-Host "Detailed log saved to: $LogPath" -ForegroundColor Cyan
Write-Log "Log file location: $LogPath" -Level "INFO"

#endregion