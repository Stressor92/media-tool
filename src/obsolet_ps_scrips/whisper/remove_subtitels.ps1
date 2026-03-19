$root = "E:\converttomkv\Arcane\Season 01"
$mkvmerge = "C:\Program Files\MKVToolNix\mkvmerge.exe"

Get-ChildItem $root -Filter "*.mkv" | ForEach-Object {

    $input  = $_.FullName
    $output = "$($_.DirectoryName)\$($_.BaseName).nosubs.mkv"

    Write-Host "Removing subtitles from $($_.Name)..."

    & $mkvmerge -o "$output" --no-subtitles "$input"

    if (Test-Path $output) {
        Remove-Item $input -Force
        Rename-Item $output $_.Name
        Write-Host " Done"
    } else {
        Write-Host "Failed"
    }
}