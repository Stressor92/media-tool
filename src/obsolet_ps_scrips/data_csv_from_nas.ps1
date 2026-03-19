$SourcePath = "Y:\"
$OutputFile = "Y:\Datei_und_Ordner_Uebersicht.csv"

Get-ChildItem -Path $SourcePath -Recurse -Force -ErrorAction SilentlyContinue |
Select-Object `
    @{Name="Pfad";Expression={$_.FullName}},
    @{Name="Dateiname";Expression={$_.Name}},
    @{Name="Erstelldatum";Expression={$_.CreationTime}},
    @{Name="Aenderungsdatum";Expression={$_.LastWriteTime}},
    @{Name="Dateityp";Expression={
        if ($_.PSIsContainer) { "Ordner" }
        else { $_.Extension }
    }} |
Export-Csv -Path $OutputFile -Delimiter ";" -NoTypeInformation -Encoding UTF8

Write-Host "Fertig! Datei wurde gespeichert unter: $OutputFile"
