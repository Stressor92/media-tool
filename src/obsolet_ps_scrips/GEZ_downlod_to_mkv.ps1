$RootPath = "C:\Users\hille\Downloads"

Get-ChildItem -Path $RootPath -Filter "*.mp4" -File | ForEach-Object {

    $source   = $_.FullName
    $baseName = $_.BaseName
    $folder   = Join-Path $RootPath $baseName
    $target   = Join-Path $folder ($baseName + ".mkv")

    # Ordner anlegen falls nicht vorhanden
    if (-not (Test-Path $folder)) {
        New-Item -ItemType Directory -Path $folder | Out-Null
    }

    # MKV nicht doppelt erstellen
    if (Test-Path $target) {
        Write-Host "Uebersprungen (existiert): $target"
        return
    }

    Write-Host "Verarbeite:"
    Write-Host $source -ForegroundColor Cyan

    ffmpeg -y -i "$source" -map 0 -c copy `
        -metadata:s:a:0 language=deu `
        -metadata:s:a:0 title=Deutsch `
        "$target"

    if ($LASTEXITCODE -eq 0) {
        Write-Host "OK: $target" -ForegroundColor Green
        # Optional: Original MP4 loeschen
        # Remove-Item "$source"
    } else {
        Write-Host "FEHLER bei: $source" -ForegroundColor Red
    }
}
