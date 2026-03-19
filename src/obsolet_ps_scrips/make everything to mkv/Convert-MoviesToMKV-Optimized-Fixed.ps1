<#
.SYNOPSIS
    High-performance MP4 to MKV converter optimized for NAS storage
.DESCRIPTION
    Converts MP4 files to MKV format with significant performance optimizations:
    - Local temp conversion (copies to local disk, converts, copies back)
    - Parallel processing of multiple files
    - Proper audio language metadata
    - Comprehensive error handling and resume capability
.PARAMETER RootPath
    The root directory to scan for MP4 files (can be NAS path like Y:\)
.PARAMETER DeleteOriginal
    If set to $false, keeps original MP4 files after conversion (default: $true)
.PARAMETER DefaultLanguage
    Default audio language to use when detection fails (default: prompts user)
.PARAMETER LocalTempPath
    Local temp directory for faster conversion (default: $env:TEMP\MovieConvert)
.PARAMETER MaxParallelJobs
    Maximum number of parallel conversion jobs (default: 2)
.PARAMETER UseLocalConversion
    Use local temp directory for conversion (significantly faster, default: $true)
.EXAMPLE
    .\Convert-MoviesToMKV-Optimized-Fixed.ps1 -RootPath "Y:\"
.EXAMPLE
    .\Convert-MoviesToMKV-Optimized-Fixed.ps1 -RootPath "\\TRUENAS\Media\Movies" -MaxParallelJobs 3
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory=$false)]
    [string]$RootPath = "E:\converttomkv",
    
    [Parameter(Mandatory=$false)]
    [bool]$DeleteOriginal = $true,
    
    [Parameter(Mandatory=$false)]
    [ValidateSet("de", "en", "prompt")]
    [string]$DefaultLanguage = "en",
    
    [Parameter(Mandatory=$false)]
    [string]$LocalTempPath = "E:\converttomkv\TEMP\MovieConvert",
    
    [Parameter(Mandatory=$false)]
    [ValidateRange(1, 8)]
    [int]$MaxParallelJobs = 1,
    
    [Parameter(Mandatory=$false)]
    [bool]$UseLocalConversion = $false
)

# Configuration
$ffmpeg  = "ffmpeg"
$ffprobe = "ffprobe"

# Language mapping from ISO 639-2 (3-letter) to ISO 639-1 (2-letter)
$LanguageMap = @{
    'eng' = 'en'
    'deu' = 'de'
    'ger' = 'de'
    'fra' = 'fr'
    'spa' = 'es'
    'ita' = 'it'
    'por' = 'pt'
    'jpn' = 'ja'
    'und' = ''
    ''    = ''
}

# Statistics (thread-safe using synchronized hashtable)
$stats = [hashtable]::Synchronized(@{
    Total = 0
    Converted = 0
    Skipped = 0
    Failed = 0
    StartTime = Get-Date
})

# Progress log file
$ProgressLog = Join-Path $LocalTempPath "conversion-progress.log"

# Function to verify FFmpeg/FFprobe availability
function Test-FFmpegAvailable {
    try {
        $null = & $ffmpeg -version 2>&1
        $null = & $ffprobe -version 2>&1
        return $true
    } catch {
        Write-Error "FFmpeg or FFprobe not found. Please install FFmpeg and ensure it's in your PATH."
        Write-Error "Download from: https://ffmpeg.org/download.html"
        return $false
    }
}

# Function to detect audio language
function Get-AudioLanguage {
    param([string]$FilePath)
    
    try {
        $langOutput = & $ffprobe `
            -v error `
            -select_streams a:0 `
            -show_entries stream_tags=language `
            -of default=nw=1:nk=1 `
            "$FilePath" 2>&1
        
        $detectedLang = ($langOutput -as [string]).Trim().ToLower()
        
        if ($LanguageMap.ContainsKey($detectedLang)) {
            return $LanguageMap[$detectedLang]
        }
        
        if ($detectedLang -match '^[a-z]{2}$') {
            return $detectedLang
        }
        
        return $null
    } catch {
        return $null
    }
}

# Function to get available disk space
function Get-FreeDiskSpace {
    param([string]$Path)
    
    try {
        $drive = (Get-Item $Path).PSDrive
        if ($drive) {
            return [math]::Round($drive.Free / 1GB, 2)
        }
    } catch {
        return 0
    }
}

# Function to prompt for language (synchronous)
function Get-UserLanguageChoice {
    param([string]$FileName)
    
    Write-Host "`nCannot determine audio language for: $FileName" -ForegroundColor Yellow
    
    do {
        $choice = Read-Host "Enter audio language - German (de), English (en), or other 2-letter code"
        $choice = $choice.Trim().ToLower()
    } while ($choice -notmatch '^[a-z]{2}$')
    
    return $choice
}

# Function to log progress
function Write-ProgressLog {
    param([string]$Message)
    
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $logMessage = "[$timestamp] $Message"
    Add-Content -Path $ProgressLog -Value $logMessage -ErrorAction SilentlyContinue
}

# Main conversion function with local temp optimization
function Convert-ToMKVOptimized {
    param(
        [System.IO.FileInfo]$File,
        [string]$Language,
        [bool]$UseLocal,
        [string]$FFmpegPath,
        [string]$FFprobePath,
        [bool]$DeleteOrig,
        [string]$TempPath,
        [string]$LogPath,
        [hashtable]$Statistics
    )

    $InputFile = $File.FullName
    $BaseName  = $File.BaseName
    $Dir       = $File.DirectoryName
    $MKVFile   = Join-Path $Dir "$BaseName.mkv"
    
    # Thread ID for logging
    $ThreadId = [System.Threading.Thread]::CurrentThread.ManagedThreadId

    # Check if MKV already exists
    if (Test-Path -LiteralPath $MKVFile) {
        Write-Host "  [$ThreadId] [SKIP] MKV already exists: $($File.Name)" -ForegroundColor Cyan
        $Statistics.Skipped++
        return $true
    }

    Write-Host "`n[$ThreadId] === Converting: $($File.Name) ===" -ForegroundColor Green
    
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $logMessage = "[$timestamp] START: $($File.Name) (Thread: $ThreadId)"
    Add-Content -Path $LogPath -Value $logMessage -ErrorAction SilentlyContinue

    try {
        # Determine working paths
        if ($UseLocal) {
            # Create unique temp directory for this conversion
            $tempConvertDir = Join-Path $TempPath "job_$ThreadId`_$([guid]::NewGuid().ToString('N').Substring(0,8))"
            New-Item -ItemType Directory -Path $tempConvertDir -Force | Out-Null
            
            $localMP4 = Join-Path $tempConvertDir "$BaseName.mp4"
            $localMKV = Join-Path $tempConvertDir "$BaseName.mkv"
            
            # Check available space
            $fileSize = $File.Length
            $requiredGB = [math]::Ceiling(($fileSize * 2.2) / 1GB)
            
            $drive = (Get-Item $tempConvertDir).PSDrive
            $availableGB = if ($drive) { [math]::Round($drive.Free / 1GB, 2) } else { 0 }
            
            if ($availableGB -lt $requiredGB) {
                Write-Warning "  [$ThreadId] [ERROR] Insufficient disk space. Need: ${requiredGB}GB, Available: ${availableGB}GB"
                Write-Host "  [$ThreadId] Falling back to direct NAS conversion..." -ForegroundColor Yellow
                Remove-Item $tempConvertDir -Recurse -Force -ErrorAction SilentlyContinue
                $UseLocal = $false
            }
        }

        if ($UseLocal) {
            # OPTIMIZED PATH: Copy to local, convert, copy back
            Write-Host "  [$ThreadId] Copying to local temp..." -ForegroundColor Cyan
            $copyStart = Get-Date
            Copy-Item -LiteralPath $InputFile -Destination $localMP4 -Force
            $copyTime = ((Get-Date) - $copyStart).TotalSeconds
            Write-Host "  [$ThreadId] Copy completed in $([math]::Round($copyTime, 1))s" -ForegroundColor Cyan
            
            $workingInput = $localMP4
            $workingOutput = $localMKV
        } else {
            # DIRECT PATH: Convert directly on NAS
            $workingInput = $InputFile
            $workingOutput = $MKVFile
        }

        # Build FFmpeg arguments
        $ffmpegArgs = @(
            '-y'
            '-i', $workingInput
            '-map', '0'
            '-c', 'copy'
        )

        # Add language metadata
        if ($Language) {
            $ffmpegArgs += @(
                '-metadata:s:a:0', "language=$Language"
                '-metadata:s:a:0', "title=Audio ($Language)"
            )
        }

        $ffmpegArgs += $workingOutput

        # Execute conversion
        Write-Host "  [$ThreadId] Converting..." -ForegroundColor Cyan
        $convertStart = Get-Date
        $output = & $FFmpegPath @ffmpegArgs 2>&1
        $convertTime = ((Get-Date) - $convertStart).TotalSeconds

        # Verify conversion
        if (-not (Test-Path -LiteralPath $workingOutput)) {
            throw "Output file not created"
        }

        $outputSize = (Get-Item -LiteralPath $workingOutput).Length
        if ($outputSize -le 0) {
            throw "Output file is empty"
        }

        Write-Host "  [$ThreadId] Conversion completed in $([math]::Round($convertTime, 1))s" -ForegroundColor Green

        # Copy back to NAS if using local conversion
        if ($UseLocal) {
            Write-Host "  [$ThreadId] Copying back to NAS..." -ForegroundColor Cyan
            $copyBackStart = Get-Date
            Copy-Item -LiteralPath $localMKV -Destination $MKVFile -Force
            $copyBackTime = ((Get-Date) - $copyBackStart).TotalSeconds
            Write-Host "  [$ThreadId] Copy back completed in $([math]::Round($copyBackTime, 1))s" -ForegroundColor Cyan
            
            $totalTime = $copyTime + $convertTime + $copyBackTime
        } else {
            $totalTime = $convertTime
        }

        Write-Host "  [$ThreadId] Total time: $([math]::Round($totalTime, 1))s" -ForegroundColor Green
        Write-Host "  [$ThreadId] Size: $([math]::Round($outputSize / 1MB, 2)) MB" -ForegroundColor Green

        # Verify stream count
        $mp4Streams = & $FFprobePath -v error -show_streams -of json "$InputFile" | ConvertFrom-Json
        $mkvStreams = & $FFprobePath -v error -show_streams -of json "$MKVFile" | ConvertFrom-Json

        if ($mp4Streams.streams.Count -ne $mkvStreams.streams.Count) {
            Write-Warning "  [$ThreadId] [WARN] Stream count mismatch - original kept"
        } elseif ($DeleteOrig) {
            Remove-Item -LiteralPath $InputFile -Force
            Write-Host "  [$ThreadId] [OK] Original MP4 deleted" -ForegroundColor Green
        }

        # Cleanup temp files
        if ($UseLocal) {
            Remove-Item $tempConvertDir -Recurse -Force -ErrorAction SilentlyContinue
        }

        $Statistics.Converted++
        $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
        $logMessage = "[$timestamp] SUCCESS: $($File.Name) in $([math]::Round($totalTime, 1))s"
        Add-Content -Path $LogPath -Value $logMessage -ErrorAction SilentlyContinue
        return $true

    } catch {
        Write-Error "  [$ThreadId] [ERROR] Conversion failed: $_"
        $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
        $logMessage = "[$timestamp] FAILED: $($File.Name) - $_"
        Add-Content -Path $LogPath -Value $logMessage -ErrorAction SilentlyContinue
        
        # Cleanup on error
        if ($UseLocal -and (Test-Path $tempConvertDir)) {
            Remove-Item $tempConvertDir -Recurse -Force -ErrorAction SilentlyContinue
        }
        if ((Test-Path $MKVFile) -and ((Get-Item $MKVFile).Length -eq 0)) {
            Remove-Item $MKVFile -Force -ErrorAction SilentlyContinue
        }
        
        $Statistics.Failed++
        return $false
    }
}


# ============================================================================
# MAIN SCRIPT EXECUTION
# ============================================================================

Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "  HIGH-PERFORMANCE Movie to MKV Converter" -ForegroundColor Cyan
Write-Host "  Optimized for NAS Storage (TrueNAS/Jellyfin)" -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host ""

# Verify FFmpeg
if (-not (Test-FFmpegAvailable)) {
    exit 1
}

# Verify root path
if (-not (Test-Path -LiteralPath $RootPath)) {
    Write-Error "Root path does not exist: $RootPath"
    exit 1
}

# Create local temp directory
if ($UseLocalConversion) {
    if (-not (Test-Path $LocalTempPath)) {
        New-Item -ItemType Directory -Path $LocalTempPath -Force | Out-Null
    }
    Write-Host "Local temp directory: $LocalTempPath" -ForegroundColor Cyan
}

# Display configuration
Write-Host "Configuration:" -ForegroundColor Cyan
Write-Host "  Root Path:           $RootPath"
Write-Host "  Delete Original:     $DeleteOriginal"
Write-Host "  Default Language:    $DefaultLanguage"
Write-Host "  Local Conversion:    $UseLocalConversion"
Write-Host "  Max Parallel Jobs:   $MaxParallelJobs"
Write-Host "  Local Temp Path:     $LocalTempPath"
Write-Host ""

# Scan for files
Write-Host "Scanning for MP4 files..." -ForegroundColor Cyan
$files = Get-ChildItem -Path $RootPath -Recurse -File | Where-Object {
    if ($_.Extension -ne ".mp4") { return $false }
    if ($_.BaseName -match "(?i)(trailer|sample|preview)") { return $false }

    $mkvPath = Join-Path $_.DirectoryName ($_.BaseName + ".mkv")
    if (Test-Path -LiteralPath $mkvPath) {
        Write-Host "  [SKIP] MKV exists: $($_.Name)" -ForegroundColor Cyan
        $stats.Skipped++
        return $false
    }

    return $true
}

$stats.Total = $files.Count

if ($stats.Total -eq 0) {
    Write-Host "No MP4 files found for conversion." -ForegroundColor Yellow
    exit 0
}

Write-Host "Found $($stats.Total) MP4 file(s) to process" -ForegroundColor Green
Write-Host ""

# Pre-detect languages for all files if not using prompt mode
$fileLanguageMap = @{}
if ($DefaultLanguage -ne "prompt") {
    Write-Host "Pre-detecting audio languages..." -ForegroundColor Cyan
    foreach ($file in $files) {
        $detectedLang = Get-AudioLanguage -FilePath $file.FullName
        $fileLanguageMap[$file.FullName] = if ($detectedLang) { $detectedLang } else { $DefaultLanguage }
    }
    Write-Host "Language detection complete.`n" -ForegroundColor Green
} else {
    # Prompt mode - ask user for each file upfront
    Write-Host "Collecting language preferences..." -ForegroundColor Cyan
    foreach ($file in $files) {
        $detectedLang = Get-AudioLanguage -FilePath $file.FullName
        if ($detectedLang) {
            $fileLanguageMap[$file.FullName] = $detectedLang
        } else {
            $fileLanguageMap[$file.FullName] = Get-UserLanguageChoice -FileName $file.Name
        }
    }
    Write-Host "Language collection complete.`n" -ForegroundColor Green
}

# Process files in parallel
Write-Host "Starting parallel conversion (max $MaxParallelJobs jobs)..." -ForegroundColor Green
Write-Host "========================================================`n" -ForegroundColor Cyan

# Create synchronized dictionary for thread-safe access
$syncFileLanguageMap = [System.Collections.Concurrent.ConcurrentDictionary[string,string]]::new()
foreach ($key in $fileLanguageMap.Keys) {
    $syncFileLanguageMap.TryAdd($key, $fileLanguageMap[$key]) | Out-Null
}

# Convert to simple values for passing to parallel block
$ffmpegPath = $ffmpeg
$ffprobePath = $ffprobe
$useLocal = $UseLocalConversion
$deleteOrig = $DeleteOriginal
$tempPath = $LocalTempPath
$logPath = $ProgressLog

$files | ForEach-Object -ThrottleLimit $MaxParallelJobs -Parallel {
    # Get all parameters from parent scope
    $file = $_
    $syncMap = $using:syncFileLanguageMap
    $lang = $syncMap[$file.FullName]
    
    # Get simple values (not script blocks)
    $ffmpeg = $using:ffmpegPath
    $ffprobe = $using:ffprobePath
    $useLocalConv = $using:useLocal
    $deleteOriginal = $using:deleteOrig
    $localTempPath = $using:tempPath
    $progressLog = $using:logPath
    $statistics = $using:stats
    
    # Define the conversion function inline
    $InputFile = $file.FullName
    $BaseName  = $file.BaseName
    $Dir       = $file.DirectoryName
    $MKVFile   = Join-Path $Dir "$BaseName.mkv"
    
    $ThreadId = [System.Threading.Thread]::CurrentThread.ManagedThreadId

    if (Test-Path -LiteralPath $MKVFile) {
        Write-Host "  [$ThreadId] [SKIP] MKV already exists: $($file.Name)" -ForegroundColor Cyan
        $statistics.Skipped++
        return
    }

    Write-Host "`n[$ThreadId] === Converting: $($file.Name) ===" -ForegroundColor Green
    
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Content -Path $progressLog -Value "[$timestamp] START: $($file.Name) (Thread: $ThreadId)" -ErrorAction SilentlyContinue

    try {
        if ($useLocalConv) {
            $tempConvertDir = Join-Path $localTempPath "job_$ThreadId`_$([guid]::NewGuid().ToString('N').Substring(0,8))"
            New-Item -ItemType Directory -Path $tempConvertDir -Force | Out-Null
            
            $localMP4 = Join-Path $tempConvertDir "$BaseName.mp4"
            $localMKV = Join-Path $tempConvertDir "$BaseName.mkv"
            
            $fileSize = $file.Length
            $requiredGB = [math]::Ceiling(($fileSize * 2.2) / 1GB)
            $drive = (Get-Item $tempConvertDir).PSDrive
            $availableGB = if ($drive) { [math]::Round($drive.Free / 1GB, 2) } else { 0 }
            
            if ($availableGB -lt $requiredGB) {
                Write-Warning "  [$ThreadId] Insufficient disk space. Need: ${requiredGB}GB, Available: ${availableGB}GB"
                Write-Host "  [$ThreadId] Falling back to direct NAS conversion..." -ForegroundColor Yellow
                Remove-Item $tempConvertDir -Recurse -Force -ErrorAction SilentlyContinue
                $useLocalConv = $false
            }
        }

        if ($useLocalConv) {
            Write-Host "  [$ThreadId] Copying to local temp..." -ForegroundColor Cyan
            $copyStart = Get-Date
            Copy-Item -LiteralPath $InputFile -Destination $localMP4 -Force
            $copyTime = ((Get-Date) - $copyStart).TotalSeconds
            Write-Host "  [$ThreadId] Copy completed in $([math]::Round($copyTime, 1))s" -ForegroundColor Cyan
            
            $workingInput = $localMP4
            $workingOutput = $localMKV
        } else {
            $workingInput = $InputFile
            $workingOutput = $MKVFile
        }

        $ffmpegArgs = @('-y', '-i', $workingInput, '-map', '0', '-c', 'copy')
        
        if ($lang) {
            $ffmpegArgs += @('-metadata:s:a:0', "language=$lang", '-metadata:s:a:0', "title=Audio ($lang)")
        }
        
        $ffmpegArgs += $workingOutput

        Write-Host "  [$ThreadId] Converting..." -ForegroundColor Cyan
        $convertStart = Get-Date
        $output = & $ffmpeg @ffmpegArgs 2>&1
        $convertTime = ((Get-Date) - $convertStart).TotalSeconds

        if (-not (Test-Path -LiteralPath $workingOutput)) {
            throw "Output file not created"
        }

        $outputSize = (Get-Item -LiteralPath $workingOutput).Length
        if ($outputSize -le 0) {
            throw "Output file is empty"
        }

        Write-Host "  [$ThreadId] Conversion completed in $([math]::Round($convertTime, 1))s" -ForegroundColor Green

        if ($useLocalConv) {
            Write-Host "  [$ThreadId] Copying back to NAS..." -ForegroundColor Cyan
            $copyBackStart = Get-Date
            Copy-Item -LiteralPath $localMKV -Destination $MKVFile -Force
            $copyBackTime = ((Get-Date) - $copyBackStart).TotalSeconds
            Write-Host "  [$ThreadId] Copy back completed in $([math]::Round($copyBackTime, 1))s" -ForegroundColor Cyan
            
            $totalTime = $copyTime + $convertTime + $copyBackTime
        } else {
            $totalTime = $convertTime
        }

        Write-Host "  [$ThreadId] Total time: $([math]::Round($totalTime, 1))s" -ForegroundColor Green
        Write-Host "  [$ThreadId] Size: $([math]::Round($outputSize / 1MB, 2)) MB" -ForegroundColor Green

        $mp4Streams = & $ffprobe -v error -show_streams -of json "$InputFile" | ConvertFrom-Json
        $mkvStreams = & $ffprobe -v error -show_streams -of json "$MKVFile" | ConvertFrom-Json

        if ($mp4Streams.streams.Count -ne $mkvStreams.streams.Count) {
            Write-Warning "  [$ThreadId] [WARN] Stream count mismatch - original kept"
        } elseif ($deleteOriginal) {
            Remove-Item -LiteralPath $InputFile -Force
            Write-Host "  [$ThreadId] [OK] Original MP4 deleted" -ForegroundColor Green
        }

        if ($useLocalConv) {
            Remove-Item $tempConvertDir -Recurse -Force -ErrorAction SilentlyContinue
        }

        $statistics.Converted++
        $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
        Add-Content -Path $progressLog -Value "[$timestamp] SUCCESS: $($file.Name) in $([math]::Round($totalTime, 1))s" -ErrorAction SilentlyContinue

    } catch {
        Write-Error "  [$ThreadId] [ERROR] Conversion failed: $_"
        $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
        Add-Content -Path $progressLog -Value "[$timestamp] FAILED: $($file.Name) - $_" -ErrorAction SilentlyContinue
        
        if ($useLocalConv -and (Test-Path $tempConvertDir)) {
            Remove-Item $tempConvertDir -Recurse -Force -ErrorAction SilentlyContinue
        }
        if ((Test-Path $MKVFile) -and ((Get-Item $MKVFile).Length -eq 0)) {
            Remove-Item $MKVFile -Force -ErrorAction SilentlyContinue
        }
        
        $statistics.Failed++
    }
}

# Calculate total time
$totalTime = ((Get-Date) - $stats.StartTime).TotalMinutes

# Display summary
Write-Host "`n========================================================" -ForegroundColor Cyan
Write-Host "  Conversion Summary" -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "  Total files found:      $($stats.Total)"
Write-Host "  Successfully converted: $($stats.Converted)" -ForegroundColor Green
Write-Host "  Skipped (exists):       $($stats.Skipped)" -ForegroundColor Cyan
Write-Host "  Failed:                 $($stats.Failed)" -ForegroundColor $(if ($stats.Failed -gt 0) { "Red" } else { "White" })
Write-Host "  Total time:             $([math]::Round($totalTime, 1)) minutes"
if ($stats.Converted -gt 0) {
    Write-Host "  Average per file:       $([math]::Round($totalTime / $stats.Converted, 1)) minutes"
}
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Progress log saved to: $ProgressLog" -ForegroundColor Cyan
