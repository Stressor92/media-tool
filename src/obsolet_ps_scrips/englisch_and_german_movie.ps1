param (
    [string]$RootPath = "C:\Users\hille\Downloads\Talk to Me (2022)"
)

# --- Einstellungen ---
$ffmpegPath = "ffmpeg"  # ffmpeg muss im PATH sein oder absoluter Pfad hier angeben

# --- Dateien suchen ---
$files = Get-ChildItem -Path $RootPath -Filter "*.mp4" -File

if ($files.Count -lt 2) {
    Write-Host "Es wurden weniger als zwei MP4-Dateien gefunden!" -ForegroundColor Red
    exit
}

# Sprachdateien erkennen (z. B. -de, _de, (de), -en, _en, (en))
$germanFile  = $files | Where-Object { $_.BaseName -match '[-_ \(\[]de[\)\]_ ]?$' }
$englishFile = $files | Where-Object { $_.BaseName -match '[-_ \(\[]en[\)\]_ ]?$' }

if (-not $germanFile -or -not $englishFile) {
    Write-Host "❌ Es wurden nicht beide Sprachversionen erkannt!" -ForegroundColor Red
    Write-Host "Gefundene Dateien:" -ForegroundColor Yellow
    $files | ForEach-Object { Write-Host " - $($_.Name)" }
    exit
}

# --- Automatisch Basisnamen bestimmen ---
$baseName = $germanFile.BaseName -replace '[-_ \(]de[\)_ ]?$', ''
$outputFile = Join-Path $RootPath ("{0}.mkv" -f $baseName)

Write-Host "🎬 Erzeuge MKV: $outputFile" -ForegroundColor Cyan

# --- ffmpeg-Befehl vorbereiten ---
$arguments = @(
    "-i", "`"$($germanFile.FullName)`"",
    "-i", "`"$($englishFile.FullName)`"",
    "-map", "0:v:0",                    # Video von der deutschen Version
    "-map", "0:a:0",                    # Deutsche Tonspur
    "-map", "1:a:0",                    # Englische Tonspur
    "-c:v", "copy",                     # Video unverändert
    "-c:a", "copy",                     # Audio unverändert
    "-metadata:s:a:0", "language=deu",
    "-metadata:s:a:1", "language=eng",
    "`"$outputFile`""
)

# --- ffmpeg ausfuehren ---
& $ffmpegPath @arguments

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ Erfolgreich erstellt: $outputFile" -ForegroundColor Green
} else {
    Write-Host "❌ Fehler bei der Konvertierung!" -ForegroundColor Red
}
