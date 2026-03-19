$basePath = "C:\Users\hille\Downloads"
$ffmpeg   = "ffmpeg"   # ggf. vollen Pfad angeben

Get-ChildItem $basePath -Recurse -Filter "*- de.mp4" | ForEach-Object {

    $deFile = $_
    $baseName = $deFile.Name -replace " - de\.mp4$", ""

    $enFile = Join-Path $deFile.DirectoryName ($baseName + " - en.mp4")
    $esFile = Join-Path $deFile.DirectoryName ($baseName + " - es.mp4")

    if (Test-Path $enFile) {
        $secondLangFile = $enFile
        $secondLangCode = "eng"
        $secondLangName = "English"
    }
    elseif (Test-Path $esFile) {
        $secondLangFile = $esFile
        $secondLangCode = "spa"
        $secondLangName = "Spanish"
    }
    else {
        Write-Host "⏭️ Überspringe (keine EN/ES): $baseName"
        return
    }

    # MKV im selben Ordner erstellen
    $outFile = Join-Path $deFile.DirectoryName ($baseName + ".mkv")

    Write-Host "🎬 Erzeuge MKV: $baseName (DE + $secondLangName)"

    & $ffmpeg `
        -i "$($deFile.FullName)" `
        -i "$secondLangFile" `
        -map 0:v:0 `
        -map 0:a:0 `
        -map 1:a:0 `
        -c copy `
        -metadata:s:a:0 language=deu `
        -metadata:s:a:1 language=$secondLangCode `
        "$outFile"

    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ Fehler bei $baseName"
    }
    else {
        Write-Host "✅ Fertig: $outFile"
    }
}
