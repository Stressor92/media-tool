# -----------------------------
# Simple MP4 -> MKV Converter
# -----------------------------
$RootPath = "C:\Users\hille\Downloads\Time Bandits (1981)"
$DefaultAudioLang = "en"   # englisch
$FFmpegPath = "ffmpeg"      # ffmpeg muss in PATH sein oder kompletten Pfad angeben

# Finde alle MP4 Dateien rekursiv
$Files = Get-ChildItem -Path $RootPath -Recurse -Filter "*.mp4"

foreach ($File in $Files) {
    $InputFile = $File.FullName
    $OutputFile = [System.IO.Path]::ChangeExtension($InputFile, ".mkv")

    Write-Host "Converting: $InputFile"

    # ffmpeg Befehl: Video kopieren, Audio auf Englisch markieren
    $Arguments = "-i `"$InputFile`" -c:v copy -c:a copy -metadata:s:a:0 language=$DefaultAudioLang `"$OutputFile`" -y"

    # ffmpeg ausführen
    $Process = Start-Process -FilePath $FFmpegPath -ArgumentList $Arguments -Wait -NoNewWindow -PassThru

    if ($Process.ExitCode -eq 0 -and (Test-Path $OutputFile) -and ((Get-Item $OutputFile).Length -gt 0)) {
        Write-Host "Success: $OutputFile"
        # Original löschen
        Remove-Item $InputFile -Force
    } else {
        Write-Warning "Failed: $InputFile"
    }
}

Write-Host "Conversion finished."
