$RootPath = "C:\Users\hille\Downloads\Test"

$ffmpeg  = "ffmpeg"
$ffprobe = "ffprobe"

# Whisper
$WhisperExe   = "C:\Program Files\Whisper\whisper-cli.exe"
$WhisperModel = "C:\Program Files\Whisper\models\ggml-large-v3.bin"

function Scale-SrtTiming {
    param(
        [string]$SrtFile,
        [double]$ScaleFactor = 1.0
    )
    Write-Host "Skaliere SRT Zeiten mit Faktor $ScaleFactor"

    $content = Get-Content $SrtFile
    $timeRegex = '^(\d{2}):(\d{2}):(\d{2}),(\d{3}) --> (\d{2}):(\d{2}):(\d{2}),(\d{3})$'

    $scaled = $content | ForEach-Object {
        if ($_ -match $timeRegex) {
            # Startzeit und Endzeit parsen
            $start = [TimeSpan]::ParseExact("$($matches[1]):$($matches[2]):$($matches[3]).$($matches[4])", "hh\:mm\:ss\.fff", $null)
            $end   = [TimeSpan]::ParseExact("$($matches[5]):$($matches[6]):$($matches[7]).$($matches[8])", "hh\:mm\:ss\.fff", $null)

            # Zeiten skalieren
            $startNewTicks = [long]($start.Ticks * $ScaleFactor)
            $endNewTicks = [long]($end.Ticks * $ScaleFactor)

            $startNew = [TimeSpan]::FromTicks($startNewTicks)
            $endNew = [TimeSpan]::FromTicks($endNewTicks)

            # Neue Zeiten formatieren
            $startStr = $startNew.ToString("hh\:mm\:ss\,fff")
            $endStr = $endNew.ToString("hh\:mm\:ss\,fff")

            "$startStr --> $endStr"
        }
        else {
            $_
        }
    }

    # Backup der Originaldatei
    Copy-Item $SrtFile "$SrtFile.bak" -Force
    # Überschreibe mit skalierten Zeiten
    $scaled | Set-Content $SrtFile -Encoding UTF8
}

Get-ChildItem -Path $RootPath -Recurse -File |
Where-Object {
    $_.Extension -match "\.(mkv|mp4)$" -and
    ($_.BaseName -notmatch "(?i)trailer")
} |
ForEach-Object {

    $InputFile = $_.FullName
    $BaseName  = [IO.Path]::GetFileNameWithoutExtension($_)
    $Dir       = $_.DirectoryName
    $MKVFile   = Join-Path $Dir "$BaseName.mkv"

    Write-Host ""
    Write-Host "=== Verarbeite: $InputFile ==="

    # MP4 → MKV konvertieren, falls nötig
    if ($_.Extension -eq ".mp4") {
        if (-not (Test-Path $MKVFile)) {

            $LangProbe = & $ffprobe -v error -select_streams a:0 `
                -show_entries stream_tags=language `
                -of default=nw=1:nk=1 "$InputFile"

            $LangProbe = ($LangProbe -as [string]).Trim().ToLower()
            if ($LangProbe -in @("eng","deu","und")) {
                $LangProbe = @{ eng="en"; deu="de"; und="" }[$LangProbe]
            }

            if (-not $LangProbe) {
                do {
                    $LangProbe = Read-Host "Audio Deutsch (de) oder Englisch (en)?"
                } while ($LangProbe -notin @("de","en"))
            }

            & $ffmpeg -y -i "$InputFile" -map 0 -c copy `
                -metadata:s:a:0 language=$LangProbe `
                -metadata:s:a:0 title="Audio ($LangProbe)" `
                "$MKVFile"

            if (Test-Path $MKVFile) {
                Remove-Item "$InputFile" -Force
            }
        }
        $InputFile = $MKVFile
    }

    # Sprache prüfen
    $Lang = & $ffprobe -v error -select_streams a:0 `
        -show_entries stream_tags=language `
        -of default=nw=1:nk=1 "$InputFile"

    $Lang = if ($null -ne $Lang) { $Lang.Trim().ToLower() } else { "" }
    if ($Lang -in @("eng","deu","und")) {
        $Lang = @{ eng="en"; deu="de"; und="" }[$Lang]
    }

    if (-not $Lang) {
        do {
            $Lang = Read-Host "Audio Deutsch (de) oder Englisch (en)?"
        } while ($Lang -notin @("de","en"))
    }

    Write-Host "Audiosprache: $Lang"

    if ($Lang -ne "en") {
        Write-Host "Kein Englisch → uebersprungen"
        continue
    }

    # Audio extrahieren
    $AudioFile = Join-Path $Dir "$BaseName.wav"
    if (-not (Test-Path $AudioFile)) {
        Write-Host "Extrahiere WAV fuer Whisper"
        & $ffmpeg -y -i "$InputFile" `
          -af "highpass=f=80,lowpass=f=8000" `
          -vn -ac 1 -ar 16000 -acodec pcm_s16le "$AudioFile"
    }

    # Whisper Untertitel generieren
    $SrtBase = Join-Path $Dir "$BaseName.whisper.en"
    $SrtFile = "$SrtBase.srt"

    if (-not (Test-Path $SrtFile)) {
        Write-Host "Generiere Whisper-Untertitel (large-v3)"
        & $WhisperExe `
          -m "$WhisperModel" `
          -l en `
          -mc 0 `
          -ml 80 `
          -tp 0 `
          -osrt `
          -f "$AudioFile"
    }

    # Dauer Film & WAV bestimmen und SRT Zeiten anpassen
    if (Test-Path $SrtFile) {
        $movieDurationSec = (& $ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$InputFile") -as [double]
        $wavDurationSec = (& $ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$AudioFile") -as [double]
        $scaleFactor = $movieDurationSec / $wavDurationSec

        if ($scaleFactor -ne 1) {
            Scale-SrtTiming -SrtFile $SrtFile -ScaleFactor $scaleFactor
        }
    }

    # SRT an MKV anhaengen
    if ((Test-Path $SrtFile) -and ((Get-Item $SrtFile).Length -gt 1024)) {
        Write-Host "Haenge Whisper-Untertitel an"

        $TempMKV = Join-Path $Dir "$BaseName.tmp.mkv"

        & $ffmpeg -y -i "$InputFile" -i "$SrtFile" `
          -map 0 -map 1 -c copy `
          -metadata:s:s:0 language=eng `
          -metadata:s:s:0 title="English (Whisper AI)" `
          "$TempMKV"

        if (Test-Path $TempMKV) {
            Move-Item "$TempMKV" "$InputFile" -Force
            Remove-Item "$AudioFile" -Force
            Remove-Item "$SrtFile" -Force
        }
    }
    else {
        Write-Host "Keine gueltige SRT → WAV bleibt erhalten"
    }
}
