$RootPath = "C:\Users\hille\Downloads\Test"
$ffmpeg  = "ffmpeg"
$ffprobe = "ffprobe"

Get-ChildItem -Path $RootPath -Recurse -File |
Where-Object {
    $_.Extension -eq ".mp4" -and
    ($_.BaseName -notmatch "(?i)trailer")
} |
ForEach-Object {

    $InputFile = $_.FullName
    $BaseName  = $_.BaseName
    $Dir       = $_.DirectoryName
    $MKVFile   = Join-Path $Dir "$BaseName.mkv"

    if (Test-Path $MKVFile) {
        Write-Host "MKV existiert bereits → übersprungen"
        return
    }

    Write-Host "`n=== Konvertiere: $InputFile ==="

    $Lang = & $ffprobe `
        -v error `
        -select_streams a:0 `
        -show_entries stream_tags=language `
        -of default=nw=1:nk=1 `
        "$InputFile"

    $Lang = ($Lang -as [string]).Trim().ToLower()

    if ($Lang -in @("eng","deu","und","")) {
        $Lang = @{
            eng = "en"
            deu = "de"
            und = ""
            ""  = ""
        }[$Lang]
    }

    if (-not $Lang) {
        do {
            $Lang = Read-Host "Audiosprache unbekannt – Deutsch (de) oder Englisch (en)?"
        } while ($Lang -notin @("de","en"))
    }

    & $ffmpeg -y `
        -i "$InputFile" `
        -map 0 `
        -c copy `
        -metadata:s:a:0 language=$Lang `
        -metadata:s:a:0 title="Audio ($Lang)" `
        "$MKVFile"

    if (Test-Path $MKVFile) {
        Remove-Item "$InputFile" -Force
        Write-Host "✔ MP4 gelöscht, MKV erstellt"
    }
}
