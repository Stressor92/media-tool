<#
.SYNOPSIS
    Converts MP4 movie files to MKV format with proper audio language metadata
.DESCRIPTION
    Recursively scans a directory for MP4 files (excluding trailers), 
    converts them to MKV while preserving all streams, and sets correct 
    audio language metadata. Original MP4 files are deleted after successful conversion.
.PARAMETER RootPath
    The root directory to scan for MP4 files
.PARAMETER DeleteOriginal
    If set to $false, keeps original MP4 files after conversion (default: $true)
.PARAMETER DefaultLanguage
    Default audio language to use when detection fails (default: prompts user)
.EXAMPLE
    .\Convert-MoviesToMKV.ps1 -RootPath "C:\Users\hille\Downloads\Test"
.EXAMPLE
    .\Convert-MoviesToMKV.ps1 -RootPath "D:\Movies" -DefaultLanguage "de" -DeleteOriginal $false
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory=$false)]
    [string]$RootPath = "Y:\",
    
    [Parameter(Mandatory=$false)]
    [bool]$DeleteOriginal = $true,
    
    [Parameter(Mandatory=$false)]
    [ValidateSet("de", "en", "prompt")]
    [string]$DefaultLanguage = "prompt"
)

# Configuration
$ffmpeg  = "ffmpeg"
$ffprobe = "ffprobe"

# Language mapping from ISO 639-2 (3-letter) to ISO 639-1 (2-letter)
$LanguageMap = @{
    'eng' = 'en'
    'deu' = 'de'
    'ger' = 'de'  # Alternative German code
    'fra' = 'fr'
    'spa' = 'es'
    'ita' = 'it'
    'por' = 'pt'
    'jpn' = 'ja'
    'und' = ''    # Undetermined
    ''    = ''
}

# Statistics
$stats = @{
    Total = 0
    Converted = 0
    Skipped = 0
    Failed = 0
}

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
    param(
        [string]$FilePath
    )
    
    try {
        $langOutput = & $ffprobe `
            -v error `
            -select_streams a:0 `
            -show_entries stream_tags=language `
            -of default=nw=1:nk=1 `
            "$FilePath" 2>&1
        
        $detectedLang = ($langOutput -as [string]).Trim().ToLower()
        
        # Map to 2-letter code
        if ($LanguageMap.ContainsKey($detectedLang)) {
            return $LanguageMap[$detectedLang]
        }
        
        # If already 2-letter code, return as-is
        if ($detectedLang -match '^[a-z]{2}$') {
            return $detectedLang
        }
        
        return $null
    } catch {
        Write-Warning "Could not detect language for: $FilePath"
        return $null
    }
}

# Function to prompt for language
function Get-UserLanguageChoice {
    param(
        [string]$FileName
    )
    
    Write-Host "`nCannot determine audio language for: $FileName" -ForegroundColor Yellow
    
    do {
        $choice = Read-Host "Enter audio language - German (de), English (en), or other 2-letter code"
        $choice = $choice.Trim().ToLower()
    } while ($choice -notmatch '^[a-z]{2}$')
    
    return $choice
}

# Function to convert file
function Convert-ToMKV {
    param(
        [System.IO.FileInfo]$File,
        [string]$Language
    )

    $InputFile = $File.FullName
    $BaseName  = $File.BaseName
    $Dir       = $File.DirectoryName
    $MKVFile   = Join-Path $Dir "$BaseName.mkv"

    # Check if MKV already exists
    if (Test-Path -LiteralPath $MKVFile) {
        Write-Host "  [SKIP] MKV already exists -> skipped" -ForegroundColor Cyan
        $script:stats.Skipped++
        return $true
    }

    Write-Host "`n=== Converting: $($File.Name) ===" -ForegroundColor Green
    Write-Host "  Input:  $InputFile"
    Write-Host "  Output: $MKVFile"
    Write-Host "  Language: $Language"

    try {
        # Build FFmpeg arguments
        $ffmpegArgs = @(
            '-y'
            '-i', $InputFile
            '-map', '0'
            '-c', 'copy'
        )

        # Add language metadata if specified
        if ($Language) {
            $ffmpegArgs += @(
                '-metadata:s:a:0', "language=$Language"
                '-metadata:s:a:0', "title=Audio ($Language)"
            )
        }

        $ffmpegArgs += $MKVFile

        # Execute conversion
        $output = & $ffmpeg @ffmpegArgs 2>&1

        # Verify conversion success
        if (Test-Path -LiteralPath $MKVFile) {

            $mkvSize = (Get-Item -LiteralPath $MKVFile).Length

            if ($mkvSize -le 0) {
                Write-Warning "  [ERROR] Output file is empty"
                Remove-Item -LiteralPath $MKVFile -Force -ErrorAction SilentlyContinue
                $script:stats.Failed++
                return $false
            }

            Write-Host "  [OK] Conversion successful" -ForegroundColor Green
            Write-Host "    Size: $([math]::Round($mkvSize / 1MB, 2)) MB"

            # Delete original if requested
            if ($DeleteOriginal) {

                $mp4Streams = & $ffprobe -v error -show_streams -of json "$InputFile" | ConvertFrom-Json
                $mkvStreams = & $ffprobe -v error -show_streams -of json "$MKVFile"  | ConvertFrom-Json

                if ($mp4Streams.streams.Count -eq $mkvStreams.streams.Count) {
                    Remove-Item -LiteralPath $InputFile -Force
                    Write-Host "  [OK] Original MP4 deleted" -ForegroundColor Green
                }
                else {
                    Write-Warning "  [WARN] StreaAm mismatch – original kept"
                }
            }
            else {
                Write-Host "  [INFO] Original MP4 kept" -ForegroundColor Yellow
            }

            $script:stats.Converted++
            return $true
        }
        else {
            Write-Warning "  [ERROR] Conversion failed - output file not created"
            Write-Warning "FFmpeg output: $output"
            $script:stats.Failed++
            return $false
        }
    }
    catch {
        Write-Error "  [ERROR] Error during conversion: $_"
        $script:stats.Failed++
        return $false
    }
}


# Main script execution
Write-Host "=======================================================" -ForegroundColor Cyan
Write-Host "  Movie to MKV Converter for TrueNAS/Jellyfin" -ForegroundColor Cyan
Write-Host "=======================================================" -ForegroundColor Cyan
Write-Host ""

# Verify FFmpeg is available
if (-not (Test-FFmpegAvailable)) {
    exit 1
}

# Verify root path exists
if (-not (Test-Path -LiteralPath $RootPath)) {
    Write-Error "Root path does not exist: $RootPath"
    exit 1
}

Write-Host "Configuration:" -ForegroundColor Cyan
Write-Host "  Root Path: $RootPath"
Write-Host "  Delete Original: $DeleteOriginal"
Write-Host "  Default Language: $DefaultLanguage"
Write-Host ""

# Get all MP4 files (excluding trailers)
Write-Host "Scanning for MP4 files..." -ForegroundColor Cyan
$files = Get-ChildItem -Path $RootPath -Recurse -File | Where-Object {

    if ($_.Extension -ne ".mp4") { return $false }
    if ($_.BaseName -match "(?i)(trailer|sample|preview)") { return $false }

    $mkvPath = Join-Path $_.DirectoryName ($_.BaseName + ".mkv")

    if (Test-Path -LiteralPath $mkvPath) {
        Write-Host "  [SKIP] MKV exists: $($_.Name)" -ForegroundColor Cyan
        $script:stats.Skipped++
        return $false
    }

    return $true
}

$stats.Total = $files.Count

if ($stats.Total -eq 0) {
    Write-Host "No MP4 files found for conversion." -ForegroundColor Yellow
    exit 0
}

Write-Host "Found $($stats.Total) MP4 file(s) to process`n" -ForegroundColor Green

# Process each file
foreach ($file in $files) {
    # Detect language
    $detectedLang = Get-AudioLanguage -FilePath $file.FullName
    
    # Determine final language to use
    $finalLang = $null
    
    if ($detectedLang) {
        $finalLang = $detectedLang
    } elseif ($DefaultLanguage -eq "prompt") {
        $finalLang = Get-UserLanguageChoice -FileName $file.Name
    } else {
        $finalLang = $DefaultLanguage
    }
    
    # Convert the file
    Convert-ToMKV -File $file -Language $finalLang
}

# Display summary
Write-Host "`n=======================================================" -ForegroundColor Cyan
Write-Host "  Conversion Summary" -ForegroundColor Cyan
Write-Host "=======================================================" -ForegroundColor Cyan
Write-Host "  Total files found:      $($stats.Total)"
Write-Host "  Successfully converted: $($stats.Converted)" -ForegroundColor Green
Write-Host "  Skipped (exists):       $($stats.Skipped)" -ForegroundColor Cyan
Write-Host "  Failed:                 $($stats.Failed)" -ForegroundColor $(if ($stats.Failed -gt 0) { "Red" } else { "White" })
Write-Host "=======================================================" -ForegroundColor Cyan