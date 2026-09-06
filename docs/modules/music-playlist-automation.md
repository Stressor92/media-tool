# Music Playlist Automation

## Zweck

Dieses Dokument definiert ein umsetzbares Konzept fuer Playlist-Erstellung in der Musikbibliothek mit folgenden Zielen:

- Smart Playlists aus Bibliotheksdaten und Tags erzeugen.
- Hits und populaere Songs ueber mehrere Datenquellen erkennen.
- Fehlende Titel optional automatisiert herunterladen.
- Keine Halluzinationen: nur regelbasierte, nachvollziehbare Entscheidungen.

## Scope und Architektur-Fit

- CLI bleibt duenn und sammelt nur Eingaben.
- Core Services enthalten Matching, Popularity-Berechnung und Playlist-Building.
- Ergebnis ist additive Automatisierung: keine erzwungene Dateiloeschung, keine intransparente KI-Entscheidung.

## Genre-Normalisierung

- Es gibt nur ein GENRE-Feld mit Mehrfachwerten (kein separates SUBGENRE-Feld).
- Subgenres werden auf kanonische Werte gemappt und um Eltern-Genres erweitert.
- Aliase und bekannte Schreibfehler werden in `config/genre_aliases.json` gepflegt.
- Parent-Relationen sind explizit in `config/genres.json` definiert.
- Unbekannte Werte bleiben im GENRE-Tag erhalten und werden in `unknown_genres.csv` gemeldet.

Beispielaufrufe:

```bash
media-tool audio normalize-genres "E:\Musik"
media-tool audio normalize-genres "E:\Musik" --apply
```

## Tag- und Bewertungsmodell

### Grundprinzip

- Songs liegen nur einmal in der zentralen Bibliothek.
- Tags beschreiben Eigenschaften eines Songs.
- Smart Playlists werden aus Tags plus Bibliotheksdaten erzeugt.
- Manuelle Playlists bleiben bewusst kuratierte Premium-Listen.
- Namensschema: `Nummer_KATEGORIE_Thema`.

### Felder

| Feld | Typ | Beispiel | Bedeutung | Pflege |
|---|---|---|---|---|
| `GENRE` | Mehrfachwert | `Rock; Alternative Rock` | Einzige Genre-Quelle inkl. Subgenre-Hierarchie | manuell/semi-automatisch |
| `MOOD` | Mehrfachwert | `Happy; Uplifting` | Stimmung | manuell |
| `CONTEXT` | Mehrfachwert | `Party; Gaming` | Situation/Verwendungszweck | manuell |
| `RATING` | Zahl `1-10` | `9` | Persoenliche Bewertung | manuell |
| `POPULARITY` | Zahl `1-10` | `8` | Allgemeine Bekanntheit/Erfolg | automatisch |
| `BPM` | Zahl | `128` | Tempo | automatisch |

## CONTEXT

| Wert | Bedeutung |
|---|---|
| `Background` | Musik, die angenehm im Hintergrund laufen kann |
| `Party` | Musik für Partys und gute Stimmung |
| `Gaming` | Musik zum Spielen allgemein |
| `Sexytime` | Musik für Sex |
| `Fantasy` | Fantasy-/Mittelalter-/Abenteuer-Atmosphäre |
| `Workout` | Musik für Sport |
| `Driving` | Musik zum Autofahren |
| `Focus` | Ruhige Atmosphäre zum lernen und Arbeiten |
| `Romantic` | Ruhige, romantische oder intime Atmosphäre |
| `90s` | ikonische Songs aus den 90er |
| `00s` | ikonische Songs aus den 00er |
| `Japanese` | japanische Songs |

## MOOD

| Wert | Bedeutung |
|---|---|
| `Chill` | Locker, entspannt, unkompliziert |
| `Relaxed` | Ruhig und beruhigend |
| `Happy` | Fröhlich und positiv |
| `Uplifting` | Motivierend und aufbauend |
| `Fun` | Verspielt, spaßig, macht gute Laune |
| `Epic` | Groß, kraftvoll, heroisch |
| `Sad` | Traurig oder emotional |
| `Melancholic` | Nachdenklich, wehmütig |
| `Aggressive` | Hart, intensiv, wütend oder konfrontativ |
| `Energetic` | Groß, kraftvoll, heroisch |
| `Dark` | Traurig oder emotional |
| `Romantic` | Nachdenklich, wehmütig |
| `Atmospheric` | Hart, intensiv, wütend oder konfrontativ |
| `Melodic` | eingängige Melodien, harmonisierte Gitarren und oft klaren Gesang |



### Definierte `CONTEXT`-Werte

`Background; Party; Gaming; Intimate; Fantasy`

### Definierte `MOOD`-Werte

`Chill; Relaxed; Happy; Uplifting; Fun; Epic; Sad; Melancholic; Aggressive`

### `RATING`-Skala

- `1` = sehr schlecht
- `5` = okay
- `7` = gut
- `8` = sehr gut
- `9` = Lieblingssong
- `10` = All-Time-Favorit

### `POPULARITY`-Skala

- `1-2` = Nische
- `3-4` = wenig bekannt
- `5-6` = mittel
- `7-8` = sehr bekannt
- `9` = grosser Hit
- `10` = ikonischer Mega-Hit

## POPULARITY-Berechnung (1-10)

### Ziel

`POPULARITY` wird deterministisch aus Chartsignalen berechnet. Keine Vermutungen, keine frei erfundenen Werte.

### Quellenstrategie

### Primaere, offiziell nutzbare Quellen

- Spotify Web API:
  - Track-Metadaten inklusive `popularity` (`0-100`).
  - Playlist-Items fuer Chart-nahe Playlists.
  - OAuth erforderlich, Rate Limits beachten.
- YouTube Data API v3:
  - Popular-Signale ueber `videos.list` und Statistikfelder.
  - API-Key/OAuth + Quota-Modell.

### Sekundaere Quellen

- Spotify Charts Website nur als manuelle Referenz, nicht als fragiles Produktions-Scraping.
- Drittseiten nur optional und mit niedrigerem Vertrauen.

### Match-Voraussetzung vor Scoring

Jeder externe Eintrag muss einem lokalen Song sauber zugeordnet werden:

1. `ISRC` exact match.
2. Normalisierter `artist+title` match plus Dauer-Toleranz.
3. Optional Fingerprint-Match mit Mindestkonfidenz.

Bei Mehrdeutigkeit wird kein automatisches POPULARITY-Update geschrieben.

### Formel

### Teilscores

- `chart_rank_score` in `[0,1]`
  - pro Quelle: `(N - rank + 1) / N`
  - ueber Quellen gewichtet mitteln
- `spotify_score` in `[0,1]`
  - `spotify_popularity / 100`
- `youtube_score` in `[0,1]`
  - aus normalisiertem `viewCount` plus optionalem Wachstumssignal im Zeitfenster

### Gesamtwert

$$
raw = 0.45 \cdot chart\_rank\_score + 0.35 \cdot spotify\_score + 0.20 \cdot youtube\_score
$$

$$
POPULARITY = clamp(1, 10, round(1 + 9 \cdot raw))
$$

### Fehlende Quellen

- Gewichte nur ueber vorhandene Quellen neu normalisieren.
- `confidence` pro Wert mitschreiben:
  - `high`: mindestens 2 unabhaengige Quellen
  - `medium`: 1 Quelle + starker Track-Match
  - `low`: 1 Quelle + schwacher Match

## Playlist-Kategorien

- `10_ROTATION_` regelmaessig hoeren und wiederentdecken
- `20_MOOD_` Stimmung
- `30_GENRE_` gezielt nach Stil
- `40_CONTEXT_` Situation/Verwendungszweck
- `50_DISCOVERY_` neue und ungespielte Musik
- `60_BESTOF_` manuell kuratierte Favoriten

## Playlist-Regeln

| Playlist | Typ | Regel |
|---|---|---|
| `10_ROTATION_Daily` | Smart | `RATING >= 7` und zuletzt gespielt `> 30` Tage |
| `10_ROTATION_Wiederentdecken` | Smart | `Play Count <= 2`, aelter als `180` Tage, `RATING >= 5` |
| `20_MOOD_Chill` | Smart | `MOOD` enthaelt `Chill` oder `Relaxed`; optional `BPM <= 120`; `RATING >= 6` |
| `20_MOOD_GuteLaune` | Smart | `MOOD` enthaelt `Happy` oder `Uplifting`; `RATING >= 7` |
| `20_MOOD_Fun` | Smart | `MOOD` enthaelt `Fun`; `RATING >= 7` |
| `20_MOOD_Epic` | Smart | `MOOD` enthaelt `Epic`; `RATING >= 6` |
| `20_MOOD_Sad` | Smart | `MOOD` enthaelt `Sad` oder `Melancholic`; `RATING >= 6` |
| `20_MOOD_Aggressiv` | Smart | `MOOD` enthaelt `Aggressive`; `RATING >= 6` |
| `30_GENRE_Metalcore` | Smart | `GENRE` enthaelt `Metalcore`; `RATING >= 6` |
| `30_GENRE_Nu-Metal` | Smart | `GENRE` enthaelt `Nu Metal`; `RATING >= 6` |
| `30_GENRE_Pop-Rock` | Smart | `GENRE` enthaelt `Pop Rock`; `RATING >= 6` |
| `30_GENRE_Indie-Rock` | Smart | `GENRE` enthaelt `Indie Rock`; `RATING >= 6` |
| `30_GENRE_DeutschRap` | Smart | `GENRE` enthaelt `German Hip-Hop`; `RATING >= 6` |
| `30_GENRE_Rap-HipHop` | Smart | `GENRE` enthaelt `Hip-Hop`; `RATING >= 6` |
| `30_GENRE_Dubstep` | Smart | `GENRE` enthaelt `Dubstep`; `RATING >= 6` |
| `30_GENRE_Swing` | Smart | `GENRE` enthaelt `Swing`; `RATING >= 6` |
| `40_CONTEXT_Background` | Smart | `CONTEXT` enthaelt `Background`; `RATING >= 6` |
| `40_CONTEXT_Party` | Smart | `CONTEXT` enthaelt `Party`; `RATING >= 7`; optional `BPM >= 100` |
| `40_CONTEXT_Gaming` | Smart | `CONTEXT` enthaelt `Gaming`; `RATING >= 6` |
| `40_CONTEXT_Intimate` | Smart | `CONTEXT` enthaelt `Intimate`; `RATING >= 6` |
| `40_CONTEXT_Fantasy` | Smart | `CONTEXT` enthaelt `Fantasy`; `RATING >= 6` |
| `50_DISCOVERY_Neu_30Tage` | Smart | in den letzten `30` Tagen hinzugefuegt |
| `50_DISCOVERY_Ungespielt` | Smart | `Play Count = 0` und aelter als `30` Tage |
| `60_BESTOF_AllTime_100` | Manuell | ca. `100` persoenliche Favoriten |

## Zusatzregeln mit POPULARITY

Diese Regeln erweitern die Liste fuer Hit/Popular-Automatisierung:

- `10_ROTATION_Daily`: optional Priorisierung nach hohem `POPULARITY` bei gleichem `RATING`.
- `40_CONTEXT_Party`: optional zusaetzlich `POPULARITY >= 7`.
- neue Liste `10_ROTATION_HitsNow`: `POPULARITY >= 8`, `RATING >= 7`, optional `BPM >= 100`.
- neue Liste `50_DISCOVERY_Emerging`: `POPULARITY in [6,7]` und positives Wachstum.

## Automatisierte Erstellung (Agent-Workflow)

### Ablauf

1. Chart-Quellen einlesen (Spotify/YouTube Adapter).
2. Tracks normalisieren (`artist`, `title`, optional `isrc`, Dauer).
3. Gegen lokale Bibliothek matchen.
4. Fehlende Titel optional ueber bestehende Download-Module beschaffen.
5. `BPM` fuer neue lokale MP3s aktualisieren (`audio tag-bpm`).
6. MP3-Lautheit angleichen (`audio mp3gain`), damit Mix/Playlist-Uebergaenge konsistent bleiben.
7. `POPULARITY` berechnen und persistieren.
8. Smart Playlist-Regeln auswerten und `.m3u` erzeugen.
9. Report schreiben: `matched`, `missing`, `ambiguous`, `updated_popularity`.

## Anti-Halluzinations-Regeln

- Keine freie Klassifikation von Popularitaet ohne Quellwert.
- Keine automatische Uebernahme bei ambiguem Match.
- Jeder Score muss Audit-Daten enthalten:
  - genutzte Quellen
  - Rohwerte
  - Formelversion
  - Match-Confidence

## Vorschlag fuer media-tool Modulstruktur

- `src/cli/playlist_cmd.py`
  - CLI-Entrypoints fuer `playlist sync`, `playlist build`, `playlist report`.
- `src/core/playlist/models.py`
  - Typen fuer ChartEntry, MatchResult, PopularityScore, PlaylistRule.
- `src/core/playlist/sources/spotify_source.py`
  - Spotify API Adapter.
- `src/core/playlist/sources/youtube_source.py`
  - YouTube API Adapter.
- `src/core/playlist/matching.py`
  - Deterministische Matching-Regeln.
- `src/core/playlist/popularity.py`
  - POPULARITY-Berechnung und Confidence.
- `src/core/playlist/rules.py`
  - Smart-Playlist-Regelauswertung.
- `src/core/playlist/export_m3u.py`
  - Ausgabe in M3U-Dateien.
- `src/core/playlist/service.py`
  - Orchestrierung der gesamten Pipeline.

## Umsetzungsplan

### Phase 1: Datenbasis und Matching

- Adapter fuer Spotify und YouTube implementieren.
- Lokales Matching mit ISRC und Artist/Title/Dauer.
- Dry-Run Report ohne Dateischreibzugriff.

### Phase 2: POPULARITY Engine

- Formel mit Gewichtung und Confidence implementieren.
- Persistenz fuer POPULARITY in lokaler Bibliotheksmetadaten-Schicht.
- Tests fuer fehlende Quellen und Grenzfaelle.

### Phase 3: Playlist Builder

- Regel-Engine fuer alle oben definierten Kategorien.
- M3U Export mit stabilem Namensschema.
- Regression-Tests fuer Regelsets.

### Phase 4: Optionaler Auto-Download

- Nur fuer `missing`-Kandidaten mit hoher Match-Sicherheit.
- Rate-Limit, Retry und Fehlerklassifikation aus Download-Modul wiederverwenden.

## Test- und Qualitaetsanforderungen

- Unit-Tests fuer:
  - Normalisierung
  - Matching
  - POPULARITY-Berechnung
  - Playlist-Regeln
- Integration-Tests mit fixture-basierten Chart-Daten.
- Jeder Lauf erzeugt maschinenlesbaren Audit-Report (JSON/CSV).

## Beispiel-Song

```
GENRE       = Pop; Rock
MOOD        = Happy; Uplifting; Fun
CONTEXT     = Party; Background
RATING      = 9
POPULARITY  = 8
BPM         = 128
```

Ein Song kann in mehreren Smart Playlists gleichzeitig erscheinen, ohne Dateiduplikate zu erzeugen.