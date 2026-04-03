#!/usr/bin/env python3
"""
Copy movies from NAS to local drive for subtitle generation.
"""

import shutil
from pathlib import Path

# List of movies to improve (from NAS Y:\ drive)
movies_to_copy = [
    r"Y:\Alien Covenant (2017)\Alien Covenant (2017)  - [DVD].mkv",
    r"Y:\Blau ist eine warme Farbe (2013)\Blau ist eine warme Farbe (2013) - [DVD].mkv",
    r"Y:\Corpse Bride (2005)\Corpse Bride (2005) - [DVD].mkv",
    r"Y:\Dark Shadows (2012)\Dark Shadows (2012).mkv",
    r"Y:\Der König der Löwen (1994)\Der König der Löwen (1994) - [DVD].mkv",
    r"Y:\Diaz - Don't Clean Up This Blood (2012)\Diaz - Don't Clean Up This Blood (2012) - [DVD].mkv",
    r"Y:\Die Schöne und das Biest (2017)\Die Schöne und das Biest (2017) - [DVD].mkv",
    r"Y:\Dog Days (2001)\Dog Days (2001) - [DVD].mkv",
    r"Y:\Don't Be Afraid of the Dark (2010)\Don't Be Afraid of the Dark (2010).mkv",
    r"Y:\ES (1990) - Part 1\ES (1990) - Part 1 - [DVD].mkv",
    r"Y:\ES (1990) - Part 2\ES (1990) - Part 2 - [DVD].mkv",
    r"Y:\Fluch der Karibik 1 (2003)\Fluch der Karibik 1 (2003) -  [DVD].mkv",
    r"Y:\Fluch der Karibik 2 (2006)\Fluch der Karibik 2 (2006) - [DVD].mkv",
    r"Y:\Fluch der Karibik 3 - Am Ende der Welt (2007)\Fluch der Karibik 3 - Am Ende der Welt (2007) - [DVD].mkv",
    r"Y:\Fluch der Karibik 4 - Fremde Gezeiten (2011)\Fluch der Karibik 4 - Fremde Gezeiten (2011) - [DVD].mkv",
    r"Y:\Ghost in the Shell (2017)\Ghost in the Shell (2017) - [DVD].mkv",
    r"Y:\Ghostbusters - Die Geisterjäger (1984)\Ghostbusters - Die Geisterjäger (1984) - [DVD].mkv",
    r"Y:\Hot Fuzz (2007)\Hot Fuzz (2007) - [DVD en].mkv",
    r"Y:\Inglourious Basterds (2009)\Inglourious Basterds (2009).mkv",
    r"Y:\Interstellar (2014)\Interstellar (2014) - [DVD].mkv",
    r"Y:\Jackass Gumball Rally 3000 (2002)\Jackass Gumball Rally 3000 (2002).mkv",
    r"Y:\Jackass Shark Week (2021)\Jackass Shark Week (2021).mkv",
    r"Y:\Jackass Shark Week 2.0 (2022)\Jackass Shark Week 2.0 (2022).mkv",
    r"Y:\Joker (2019)\Joker (2019) - [DVD].mkv",
    r"Y:\Jurassic Park 1 (1993)\Jurassic Park 1 (1993) - [DVD].mkv",
    r"Y:\Jurassic Park 2 - The Lost World (1997)\Jurassic Park 2 - The Lost World (1997) - [DVD].mkv",
    r"Y:\Jurassic Park 3 (2001)\Jurassic Park 3 (2001)  - [DVD].mkv",
    r"Y:\Jurassic World (2015)\Jurassic World (2015)  - [DVD].mkv",
    r"Y:\Phantastische Tierwesen Grindelwalds Verbrechen (2018)\Phantastische Tierwesen Grindelwalds Verbrechen (2018) - [DVD].mkv",
    r"Y:\Phantastische Tierwesen und wo sie zu finden sind (2016)\Phantastische Tierwesen und wo sie zu finden sind (2016) - [DVD].mkv",
    r"Y:\Pinched (2010)\Pinched (2010) - [short film].mkv",
    r"Y:\Pleasure (2021)\Pleasure (2021) - [en].mkv",
    r"Y:\Pokemon\Pokémon – Der Film Geheimnisse des Dschungels (2020).mkv",
    r"Y:\Prometheus (2012)\Prometheus (2012) - [DVD].mkv",
    r"Y:\Pulp Fiction (1996)\Pulp Fiction (1994) - [en].mkv",
    r"Y:\Ratatouille (2007)\Ratatouille (2007) - [DVD].mkv",
    r"Y:\Salad Fingers\Salad Fingers.mkv",
    r"Y:\Sita Sings the Blues (2008)\Sita Sings the Blues (2008).mkv",
    r"Y:\Spider-Man Far from Home (2019)\Spider-Man Far from Home (2019) - [DVD].mkv",
    r"Y:\Spider-Man No Way Home (2021)\Spider-Man No Way Home (2021) - [DVD].mkv",
    r"Y:\Star Wars - Solo A Star Wars Story (2018)\Star Wars - Solo A Star Wars Story (2018) - [DVD].mkv",
    r"Y:\Super 8 (2011)\Super 8 (2011) - [DVD].mkv",
    r"Y:\The Father (2020)\The Father (2020)  - trailer.mkv",
    r"Y:\The Father (2020)\The Father (2020) - [en].mkv",
    r"Y:\The Lego Movie (2014)\The Lego Movie (2014) - [DVD].mkv",
    r"Y:\The Matrix (1999)\The Matrix (1999)  - [DVD].mkv",
    r"Y:\The Matrix Reloaded (2003)\The Matrix Reloaded (2003) - [DVD].mkv",
    r"Y:\The Matrix Revolutions (2003)\The Matrix Revolutions (2003) - [DVD].mkv",
    r"Y:\The Neverending Story (1984)\The Neverending Story (1984)  - [en].mkv",
    r"Y:\The Revenant (2015)\The Revenant (2015) - [DVD].mkv",
    r"Y:\The Shape of Water (2017)\The Shape of Water (2017) - [DVD].mkv",
    r"Y:\The Spirit (2008)\The Spirit (2008).mkv",
    r"Y:\Time Bandits (1981)\Time Bandits (1981) - [en].mkv",
    r"Y:\Toy Story (1995)\Toy Story (1995)  - [DVD].mkv",
    r"Y:\Toy Story 2 (1999)\Toy Story 2 (1999) - [DVD].mkv",
    r"Y:\Toy Story 3 (2010)\Toy Story 3 (2010) - [DVD].mkv",
    r"Y:\Up (2009)\Up (2009) - [DVD].mkv",
    r"Y:\WALL·E (2008)\WALL·E (2008) - [DVD].mkv",
    r"Y:\Weiße Weihnacht (1954)\Weiße Weihnacht (1954) - [DVD].mkv",
]

# Target folder
target_folder = Path(r"C:\Users\hille\Downloads\subtitle_movies")

# Create target folder if it doesn't exist
target_folder.mkdir(parents=True, exist_ok=True)

# Copy each movie to target folder
copied = 0
failed = 0

print(f"Copying {len(movies_to_copy)} movies to {target_folder}\n")

for movie_path in movies_to_copy:
    source = Path(movie_path)

    if not source.exists():
        print(f"❌ Not found: {source.name}")
        failed += 1
        continue

    try:
        target_file = target_folder / source.name
        shutil.copy2(source, target_file)
        print(f"✓ Copied: {source.name}")
        copied += 1
    except Exception as e:
        print(f"❌ Error copying {source.name}: {e}")
        failed += 1

print(f"\n✓ Done: {copied} files copied, {failed} failed")
