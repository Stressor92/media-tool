param(
    [string]$RootPath = "Y:\"
)

$yt_dlp = "yt-dlp"

# Alle Unterordner ermitteln
$movieFolders = Get-ChildItem -Path $RootPath -Directory

if ($movieFolders.Count -eq 0) {
    Write-Host "Keine Unterordner gefunden in $RootPath" -ForegroundColor Yellow
    exit
}

$counter = 0
$total = $movieFolders.Count

foreach ($folder in $movieFolders) {
    $counter++
    $movieName = $folder.Name
    $outputTemplate = Join-Path $folder.FullName "$movieName - trailer-%(id)s.%(ext)s"
    $finalName = Join-Path $folder.FullName "$movieName - trailer.mp4"
    $search = "$movieName official trailer"

    Write-Host ""
    Write-Host "[$counter/$total] Processing: $movieName"
    Write-Host "------------------------------------------------------------"

    if (Test-Path $finalName) {
        Write-Host "Trailer existiert bereits -> überspringen" -ForegroundColor DarkGray
        continue
    }

    $ytArgs = @(
        "ytsearch1:$search",
        "-o", $outputTemplate,
        "-f", "best[ext=mp4][acodec!=none]/best",
        "--no-playlist",
        "--merge-output-format", "mp4"
    )

    Write-Host "Running yt-dlp with arguments:"
    $ytArgs | ForEach-Object { Write-Host " $_" }

    try {
        $output = & $yt_dlp @ytArgs 2>&1
        Write-Host "--- yt-dlp output ---"
        Write-Host $output
        Write-Host "---------------------"

        $downloadedFiles = Get-ChildItem -Path $folder.FullName -Filter "$movieName - trailer-*.mp4" -File -ErrorAction SilentlyContinue
        if ($downloadedFiles.Count -gt 0) {
            Rename-Item -Path $downloadedFiles[0].FullName -NewName "$movieName - trailer.mp4"
            Write-Host "Trailer erfolgreich heruntergeladen und umbenannt." -ForegroundColor Green
        }
        else {
            Write-Host "WARNUNG: Kein Trailer nach Download gefunden." -ForegroundColor Yellow
        }
    }
    catch {
        Write-Host "FEHLER beim Download von $movieName" -ForegroundColor Red
        Write-Host $_.Exception.Message
    }

    Write-Host "------------------------------------------------------------"
}

Write-Host ""
Write-Host "Fertig mit allen Ordnern."
