# NAS-Pfad festlegen
$RootPath = "E:\Filme"

# Mögliche Video-Endungen
$VideoExtensions = @("*.mp4", "*.mkv", "*.avi")

# Ergebnisliste
$FilmListe = @()

# Pfad zu ffprobe.exe
$FFprobePath = "C:\Program Files\ffmpeg-8.0-full_build\bin\ffprobe.exe"

Write-Host "Suche nach Videos in $RootPath ..." -ForegroundColor Cyan

$FileCount = 0

foreach ($Ext in $VideoExtensions) {
    Write-Host " Durchsuche nach $Ext Dateien..." -ForegroundColor Yellow

    Get-ChildItem -Path $RootPath -Recurse -File -Include $Ext -ErrorAction SilentlyContinue | ForEach-Object {
        $FileCount++
        Write-Host "[$FileCount] Analysiere: $($_.FullName)" -ForegroundColor DarkGray

        $FilePath = $_.FullName
        $Extension = $_.Extension
        $FileSizeBytes = $_.Length
        $FileSizeGB = [math]::Round($FileSizeBytes / 1GB, 2)

        try {
            # ffprobe JSON-Infos holen
            $ProbeRaw = & "$FFprobePath" -v quiet -print_format json -show_format -show_streams "$FilePath" 2>&1
            $Probe = $ProbeRaw | ConvertFrom-Json

            if (-not $Probe) {
                throw "ffprobe lieferte keine gültigen Daten: $ProbeRaw"
            }

            # Video-Stream auslesen
            $VideoStream = $Probe.streams | Where-Object { $_.codec_type -eq "video" } | Select-Object -First 1
            $AudioStreams = $Probe.streams | Where-Object { $_.codec_type -eq "audio" }
            $SubtitleStreams = $Probe.streams | Where-Object { $_.codec_type -eq "subtitle" }

            # Aufbereitung der Infos
            $VideoCodec   = $VideoStream.codec_name
            $Width        = $VideoStream.width
            $Height       = $VideoStream.height
            $Resolution   = if ($Width -and $Height) { "$Width x $Height" } else { "Unbekannt" }

            $FPS = if ($VideoStream.r_frame_rate) { 
                try {
                    $fr = $VideoStream.r_frame_rate -split "/"
                    if ($fr.Count -eq 2 -and [int]$fr[1] -ne 0) {
                        [math]::Round([double]$fr[0] / [double]$fr[1], 2)
                    } else {
                        $VideoStream.r_frame_rate
                    }
                } catch { $VideoStream.r_frame_rate }
            } else { "?" }

            $AudioCount   = $AudioStreams.Count
            $AudioLangs   = ($AudioStreams | ForEach-Object { $_.tags.language }) -join ", "
            if (-not $AudioLangs) { $AudioLangs = "-" }

            $SubtitleCount = $SubtitleStreams.Count
            $SubtitleLangs = ($SubtitleStreams | ForEach-Object { $_.tags.language }) -join ", "
            if (-not $SubtitleLangs) { $SubtitleLangs = "-" }

            $DurationSec = [math]::Round([double]$Probe.format.duration, 0)
            $Duration    = "{0:D2}:{1:D2}:{2:D2}" -f ([int]($DurationSec/3600)), ([int](($DurationSec/60) % 60)), ([int]($DurationSec % 60))

            # Ergebnis speichern (angepasste Spaltenreihenfolge)
            $FilmListe += [PSCustomObject]@{
                DateiName           = $_.Name
                Pfad                = $FilePath
                Typ                 = $Extension
                Dateigroesse_GB     = $FileSizeGB
                Dauer               = $Duration
                VideoCodec          = $VideoCodec
                Aufloesung          = $Resolution
                FPS                 = $FPS
                AudioSpuren         = $AudioCount
                AudioSprachen       = $AudioLangs
                UntertitelSpuren    = $SubtitleCount
                UntertitelSprachen  = $SubtitleLangs
            }
        } catch {
            Write-Host " Fehler bei Analyse von: $FilePath" -ForegroundColor Red
            Write-Host "   Details: $($_.Exception.Message)" -ForegroundColor DarkRed
        }
    }
}  # <-- Diese Klammer fehlte vorher!

# Ergebnis exportieren
if ($FilmListe.Count -gt 0) {
    $OutputFile = "$env:USERPROFILE\Desktop\FilmListe_lowbob.csv"
    $FilmListe | Export-Csv -Path $OutputFile -NoTypeInformation -Encoding UTF8 -Delimiter ";"
    Write-Host "Fertig! $($FilmListe.Count) Dateien gefunden."
    Write-Host "Liste gespeichert unter: $OutputFile" -ForegroundColor Green
} else {
    Write-Host "Keine Videos gefunden." -ForegroundColor Yellow
}
