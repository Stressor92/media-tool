param(
    [string]$InputFolder = "C:\Users\hille\Downloads"
)

$ffmpeg  = "ffmpeg"
$ffprobe = "ffprobe"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$LogFile   = Join-Path $ScriptDir "DVD_Upscale_Log.txt"

"===== DVD Upscale Log - $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') =====" | Out-File -FilePath $LogFile -Encoding UTF8

function Log-Info {
    param($msg)
    $t = "{0} INFO: {1}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $msg
    $t | Add-Content $LogFile
    Write-Host $msg
}
function Log-Error {
    param($msg)
    $t = "{0} ERROR: {1}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $msg
    $t | Add-Content $LogFile
    Write-Host $msg -ForegroundColor Red
}

function Is-Anime {
    param([string]$name)
    $l = $name.ToLower()
    if ($l -match "anime|ova|episode|ep[0-9]{1,3}|crunchyroll|funimation|subbed|simulcast|dubbed|anime\-") {
        return $true
    }
    return $false
}

function Get-DAR {
    param([string]$file)
    $json = & $ffprobe -v error -select_streams v:0 -show_entries stream=width,height,sample_aspect_ratio -of json $file 2>$null
    if (-not $json) { return $null }
    $probe = $json | ConvertFrom-Json
    $w = [double]$probe.streams[0].width
    $h = [double]$probe.streams[0].height
    $sar = $probe.streams[0].sample_aspect_ratio
    if ($sar -and $sar -match "(\d+):(\d+)") {
        $sarVal = [double]$matches[1] / [double]$matches[2]
    } else {
        $sarVal = 1.0
    }
    $dar = ($w * $sarVal) / $h
    return @{ dar = $dar; iw = [int]$w; ih = [int]$h; sar = $sarVal }
}

function Get-CropDetect {
    param([string]$file)
    $out = & $ffmpeg -ss 5 -t 10 -i $file -vf "cropdetect=24:16:1" -f null - 2>&1 |
           Select-String -Pattern "crop=\d+:\d+:\d+:\d+" -AllMatches |
           ForEach-Object { $_.Matches } |
           ForEach-Object { $_.Value } |
           Select-Object -Last 1
    if ($out -and $out -match "crop=(\d+):(\d+):(\d+):(\d+)") {
        return @{
            raw = $out;
            cw = [int]$matches[1];
            ch = [int]$matches[2];
            cx = [int]$matches[3];
            cy = [int]$matches[4]
        }
    }
    return $null
}

function Is-CropPlausible {
    param(
        [int]$iw,
        [int]$ih,
        [int]$cw,
        [int]$ch
    )
    if ($cw -lt 320 -or $ch -lt 200) { return $false }

    $wRatio = [double]$cw / [double]$iw
    $hRatio = [double]$ch / [double]$ih

    $isLetterbox = ($wRatio -ge 0.94) -and ($hRatio -lt 0.995)
    $isPillarbox = ($hRatio -ge 0.94) -and ($wRatio -lt 0.995)

    if ($isLetterbox -and -not $isPillarbox) { return $true }
    if ($isPillarbox -and -not $isLetterbox) { return $true }

    return $false
}

Get-ChildItem -Path $InputFolder -Filter *.mkv -Recurse |
    Where-Object { $_.BaseName -notmatch "\[DVD\]$" } |
    ForEach-Object {

    $file = $_.FullName
	$parentDir = $_.DirectoryName
	$name      = $_.BaseName

	# Zielordner = Filmname
	$movieDir  = Join-Path $parentDir $name

	# Ordner anlegen, falls er noch nicht existiert
	if (-not (Test-Path $movieDir)) {
		New-Item -ItemType Directory -Path $movieDir | Out-Null
	}

	# Zieldatei im Film-Unterordner
	$output = Join-Path $movieDir ("{0} - [DVD].mkv" -f $name)

    Write-Host ""
    Write-Host "======================================================"
    Write-Host "Datei: $name"
    Write-Host "Pfad:  $file"
    Write-Host "------------------------------------------------------"

    try {
        $probeJson = & $ffprobe -v error -select_streams v:0 -show_entries stream=width,height,codec_name -of json $file 2>$null
    } catch {
        Log-Error ("ffprobe failed for {0}" -f $file)
        return
    }
    if (-not $probeJson) {
        Log-Error ("ffprobe lieferte keine Daten, überspringe Datei: {0}" -f $file)
        return
    }

    $probe = $probeJson | ConvertFrom-Json
    if (-not $probe.streams -or $probe.streams.Count -lt 1) {
        Log-Error ("Keine Videostream-Infos gefunden, überspringe: {0}" -f $file)
        return
    }

    $width  = [int]$probe.streams[0].width
    $height = [int]$probe.streams[0].height
    $codec  = $probe.streams[0].codec_name

    Log-Info ("Video: {0}x{1}, Codec: {2}" -f $width, $height, $codec)

    if ($height -ge 720) {
        Log-Info ("Übersprungen (>=720p): {0}" -f $file)
        return
    }

    $isAnime = Is-Anime $name
    if ($isAnime) {
        Log-Info ("Anime erkannt: Cropdetect deaktiviert für {0}" -f $name)
    }

    $darInfo = Get-DAR $file
    if (-not $darInfo) {
        Log-Error ("DAR konnte nicht bestimmt werden, überspringe Datei: {0}" -f $file)
        return
    }
    $dar = [double]$darInfo.dar
    $iw  = [int]$darInfo.iw
    $ih  = [int]$darInfo.ih
    Log-Info ("DAR = {0:N4}, iw={1}, ih={2}" -f $dar, $iw, $ih)

    $cropFilter = $null
    if (-not $isAnime) {
        $cd = Get-CropDetect $file
        if ($cd) {
            $cw = $cd.cw; $ch = $cd.ch; $cx = $cd.cx; $cy = $cd.cy
            Log-Info ("cropdetect Ergebnis: cw=$cw, ch=$ch, cx=$cx, cy=$cy")

            if (Is-CropPlausible -iw $iw -ih $ih -cw $cw -ch $ch) {
                $cropFilter = "crop=${cw}:${ch}:${cx}:${cy}"
                Log-Info ("Crop akzeptiert: $cropFilter")
            } else {
                Log-Info ("Crop ignoriert (nicht plausibel).")
            }
        } else {
            Log-Info ("Kein Cropdetect Ergebnis.")
        }
    }

    $filters = @()
    if ($cropFilter) { $filters += $cropFilter }

    # Skaliere auf Höhe 720, Breite passend zum DAR (breite = gerade Zahl!)

	$filters += "scale=trunc(720*dar/2)*2:720:flags=lanczos"

	# Sanftes Debanding 
	$filters += "gradfun=4"

	# Leichte Farbkorrektur
	$filters += "eq=contrast=1.02:brightness=0.00:saturation=1.02"

	# Sehr sanftes Schärfen
	$filters += "unsharp=5:5:0.25:5:5:0.0"

	# Saubere DVD-Ausgabe
	$filters += "format=yuv420p"

    $vf = $filters -join ","

    Log-Info ("Finaler Filtergraph: $vf")

    try {
        $sizeBefore = [math]::Round(((Get-Item $file).Length / 1GB), 3)
    } catch {
        $sizeBefore = 0
    }

    Log-Info ("Starte Upscale: {0} -> {1}" -f $file, $output)
    Log-Info ("CRF=21, libx265, preset=medium")

    $args = @(
        "-y",
        "-i", $file,
        "-map", "0",
        "-vf", $vf,
        "-c:v", "libx265",
        "-crf", "21",
        "-preset", "medium",
        "-c:a", "copy",
        "-c:s", "copy",
        "-map_metadata", "0",
        "-map_chapters", "0",
        $output
    )

    $start = Get-Date
    try {
        & $ffmpeg @args
        $rc = $LASTEXITCODE
    } catch {
        Log-Error ("ffmpeg fehlgeschlagen: {0}" -f $_.Exception.Message)
        $rc = 1
    }
    $duration = (New-TimeSpan -Start $start -End (Get-Date)).ToString()

    if (($rc -eq 0) -and (Test-Path $output)) {
        $sizeAfter = [math]::Round(((Get-Item $output).Length / 1GB), 3)
        $reduction = $sizeBefore - $sizeAfter
        Log-Info ("Erfolg: Ausgabe erstellt: {0}" -f $output)
        Log-Info ("   Before: {0:N3} GB, After: {1:N3} GB, Delta: {2:N3} GB, Dauer: {3}" -f $sizeBefore, $sizeAfter, $reduction, $duration)
    } else {
        Log-Error ("Upscale fehlgeschlagen für {0} (rc={1}). Dauer: {2}" -f $file, $rc, $duration)
    }

    Write-Host "------------------------------------------------------"
}

Write-Host ""
Write-Host "Fertig! Logdatei unter:"
Write-Host $LogFile
