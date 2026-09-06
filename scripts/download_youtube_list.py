import re
import subprocess
import sys
import time
from pathlib import Path

# Rohdaten mit gemischten Formaten (Markdown-Links + Plain-URLs).
RAW_LINK_INPUT = """
[https://www.youtube.com/watch?v=YaEBglkCFVc&list=PLif2iIyBTjSJlCO_lJJ5lkMvwMjRtNBo_](https://www.youtube.com/watch?v=YaEBglkCFVc&list=PLif2iIyBTjSJlCO_lJJ5lkMvwMjRtNBo_)
[https://www.youtube.com/watch?v=cW8VLC9nnTo&list=PLsCPTY_MPoPbCftVtuvquFs9ayLDwD237](https://www.youtube.com/watch?v=cW8VLC9nnTo&list=PLsCPTY_MPoPbCftVtuvquFs9ayLDwD237)
[https://www.youtube.com/watch?v=TIy3n2b7V9k&list=PLmyAPRLQRJ6lMbAdXYGuyZ627Y9RoX25i](https://www.youtube.com/watch?v=TIy3n2b7V9k&list=PLmyAPRLQRJ6lMbAdXYGuyZ627Y9RoX25i)
[https://www.youtube.com/watch?v=7wtfhZwyrcc&list=RDEMzMxPuaGyofN40xcgHuZAbw&start_radio=1](https://www.youtube.com/watch?v=7wtfhZwyrcc&list=RDEMzMxPuaGyofN40xcgHuZAbw&start_radio=1)
[https://www.youtube.com/watch?v=q7KcLlpLcdg&list=PL34DAE94F1BFEFB8A](https://www.youtube.com/watch?v=q7KcLlpLcdg&list=PL34DAE94F1BFEFB8A)
[https://www.youtube.com/watch?v=4ubWwW9RUUw&list=PLUB1ektkHn7RqZ_qkQL4Cehufy1wq7DNa](https://www.youtube.com/watch?v=4ubWwW9RUUw&list=PLUB1ektkHn7RqZ_qkQL4Cehufy1wq7DNa)
[https://www.youtube.com/watch?v=D1NdGBldg3w&list=RDEM9bvfNCNqbQ4iScFk23dYAg&start_radio=1](https://www.youtube.com/watch?v=D1NdGBldg3w&list=RDEM9bvfNCNqbQ4iScFk23dYAg&start_radio=1)
[https://www.youtube.com/watch?v=r6L-GUOAhGo&list=RDEMtLx6cWShWhH58jkEvCW70w&start_radio=1](https://www.youtube.com/watch?v=r6L-GUOAhGo&list=RDEMtLx6cWShWhH58jkEvCW70w&start_radio=1)
[https://www.youtube.com/watch?v=dcGKVnEbi8E&list=PL2Gc4X16NxB6gD0ivvjl2ZXShzIMczAvh](https://www.youtube.com/watch?v=dcGKVnEbi8E&list=PL2Gc4X16NxB6gD0ivvjl2ZXShzIMczAvh)
[https://www.youtube.com/watch?v=HyHNuVaZJ-k&list=RDEMRDrhDBv7g5VJA7vBZM1bjg&start_radio=1](https://www.youtube.com/watch?v=HyHNuVaZJ-k&list=RDEMRDrhDBv7g5VJA7vBZM1bjg&start_radio=1)
[https://www.youtube.com/watch?v=fgT9zGkiLig&list=RDEM9656AIt7PnAeA2q1XsF22g&start_radio=1](https://www.youtube.com/watch?v=fgT9zGkiLig&list=RDEM9656AIt7PnAeA2q1XsF22g&start_radio=1)
[https://www.youtube.com/watch?v=oKsxPW6i3pM&list=RDEM95kZZf9bjylNDs08ku5a8Q&start_radio=1](https://www.youtube.com/watch?v=oKsxPW6i3pM&list=RDEM95kZZf9bjylNDs08ku5a8Q&start_radio=1)
[https://www.youtube.com/watch?v=SBjQ9tuuTJQ&list=RDEMx2SPzeaRXiOzpOe0SxPVJA&start_radio=1](https://www.youtube.com/watch?v=SBjQ9tuuTJQ&list=RDEMx2SPzeaRXiOzpOe0SxPVJA&start_radio=1)
[https://www.youtube.com/watch?v=xFrGuyw1V8s&list=RDEMiMPRAwzvbVB9F1ixipdbgQ&start_radio=1](https://www.youtube.com/watch?v=xFrGuyw1V8s&list=RDEMiMPRAwzvbVB9F1ixipdbgQ&start_radio=1)
[https://www.youtube.com/watch?v=v2AC41dglnM&list=RDEMDs8vWIQKMflBG8QUQQaUrw&start_radio=1](https://www.youtube.com/watch?v=v2AC41dglnM&list=RDEMDs8vWIQKMflBG8QUQQaUrw&start_radio=1)

[https://www.youtube.com/watch?v=nWK0kqjPSVI&list=RDEMlFmuWg-cvYUex099D5Hn5A&start_radio=1](https://www.youtube.com/watch?v=nWK0kqjPSVI&list=RDEMlFmuWg-cvYUex099D5Hn5A&start_radio=1)
[https://www.youtube.com/watch?v=NCtzkaL2t_Y&list=RDEMDwfWqCd9jXCuVO7pjkJHTw&start_radio=1](https://www.youtube.com/watch?v=NCtzkaL2t_Y&list=RDEMDwfWqCd9jXCuVO7pjkJHTw&start_radio=1)
[https://www.youtube.com/watch?v=ZaI2IlHwmgQ&list=RDEMu9tGLYSdWUcyhFk3VKJzbA&start_radio=1](https://www.youtube.com/watch?v=ZaI2IlHwmgQ&list=RDEMu9tGLYSdWUcyhFk3VKJzbA&start_radio=1)
[https://www.youtube.com/watch?v=vx2u5uUu3DE&list=RDEMwFsYW_I6KW9l_k_U6XwJXQ&start_radio=1](https://www.youtube.com/watch?v=vx2u5uUu3DE&list=RDEMwFsYW_I6KW9l_k_U6XwJXQ&start_radio=1)
[https://www.youtube.com/watch?v=6Ejga4kJUts&list=RDEMkK2NSs_F78yYrJZkDQpdgg&start_radio=1](https://www.youtube.com/watch?v=6Ejga4kJUts&list=RDEMkK2NSs_F78yYrJZkDQpdgg&start_radio=1)
[https://www.youtube.com/watch?v=09R8_2nJtjg&list=RDEM4pYJp7xJSejhXY9TYgUzPw&start_radio=1](https://www.youtube.com/watch?v=09R8_2nJtjg&list=RDEM4pYJp7xJSejhXY9TYgUzPw&start_radio=1)
[https://www.youtube.com/watch?v=GemKqzILV4w&list=RDEMH2pgKpOYqT13redTdbl0Og&start_radio=1](https://www.youtube.com/watch?v=GemKqzILV4w&list=RDEMH2pgKpOYqT13redTdbl0Og&start_radio=1)
[https://www.youtube.com/watch?v=gJLIiF15wjQ&list=RDEMZt_G1RmOYuF5WTO_iIuPLA&start_radio=1](https://www.youtube.com/watch?v=gJLIiF15wjQ&list=RDEMZt_G1RmOYuF5WTO_iIuPLA&start_radio=1)
[https://www.youtube.com/watch?v=IMyv2QJCyt4&list=RDEMd5WhghrzA_2P4jbhk14QmA&start_radio=1](https://www.youtube.com/watch?v=IMyv2QJCyt4&list=RDEMd5WhghrzA_2P4jbhk14QmA&start_radio=1)
[https://www.youtube.com/watch?v=yyfrDwEb9NA&list=PLLSefGx9z0mUzC5PQuoXxMjQl2UWdGggb](https://www.youtube.com/watch?v=yyfrDwEb9NA&list=PLLSefGx9z0mUzC5PQuoXxMjQl2UWdGggb)
V
[https://www.youtube.com/watch?v=PvM79DJ2PmM&list=PLPNKnwlz-OnZcgTuCwVCcqx-1BdW2xDm1](https://www.youtube.com/watch?v=PvM79DJ2PmM&list=PLPNKnwlz-OnZcgTuCwVCcqx-1BdW2xDm1)
[https://www.youtube.com/watch?v=3ea_7J1hffs&list=PLWZNznjtG8Ye0AgOuzkXsnmqbseq2F-fd](https://www.youtube.com/watch?v=3ea_7J1hffs&list=PLWZNznjtG8Ye0AgOuzkXsnmqbseq2F-fd)
[https://www.youtube.com/watch?v=3YxaaGgTQYM&list=PLD268299DB70A4BDA](https://www.youtube.com/watch?v=3YxaaGgTQYM&list=PLD268299DB70A4BDA)
[https://www.youtube.com/watch?v=1y43uwHzLnA&list=PLf3H3jTbGY70GgZbB7Zsxg6ziLui6ZANT](https://www.youtube.com/watch?v=1y43uwHzLnA&list=PLf3H3jTbGY70GgZbB7Zsxg6ziLui6ZANT)
[https://www.youtube.com/watch?v=LJ2t4jfVTiU&list=PLxA687tYuMWjEqvg_eXIi_8eRa9AiRq9w](https://www.youtube.com/watch?v=LJ2t4jfVTiU&list=PLxA687tYuMWjEqvg_eXIi_8eRa9AiRq9w)

[https://www.youtube.com/watch?v=HXbZN701HJw&list=PLmB8EzU36iC7F9uOQ97GSt9M3enO9e4Bn](https://www.youtube.com/watch?v=HXbZN701HJw&list=PLmB8EzU36iC7F9uOQ97GSt9M3enO9e4Bn)
[https://www.youtube.com/watch?v=zinzdAA1ebo&list=PLjefIJSHHvt8FkxfOahea5rVZI2kr0sUK](https://www.youtube.com/watch?v=zinzdAA1ebo&list=PLjefIJSHHvt8FkxfOahea5rVZI2kr0sUK)
[https://www.youtube.com/watch?v=c8cKN1rbJl4&list=PLYP5MOE5S1ddXUhuVdPGZzl-2NJ22kAC7](https://www.youtube.com/watch?v=c8cKN1rbJl4&list=PLYP5MOE5S1ddXUhuVdPGZzl-2NJ22kAC7)
[https://www.youtube.com/watch?v=OX60FkTuVwM&list=RDOX60FkTuVwM&start_radio=1](https://www.youtube.com/watch?v=OX60FkTuVwM&list=RDOX60FkTuVwM&start_radio=1)
[https://www.youtube.com/watch?v=7TSP1BT2Duo&list=RD7TSP1BT2Duo&start_radio=1](https://www.youtube.com/watch?v=7TSP1BT2Duo&list=RD7TSP1BT2Duo&start_radio=1)
[https://www.youtube.com/watch?v=EfKm4k3COxw&list=PLf1NlfaLfeQhPOZKxyGVGG3QPXzhYp9Uw](https://www.youtube.com/watch?v=EfKm4k3COxw&list=PLf1NlfaLfeQhPOZKxyGVGG3QPXzhYp9Uw)
[https://www.youtube.com/watch?v=zaDbG9Ik-ZA&list=RDzaDbG9Ik-ZA&start_radio=1](https://www.youtube.com/watch?v=zaDbG9Ik-ZA&list=RDzaDbG9Ik-ZA&start_radio=1)
[https://www.youtube.com/watch?v=GkD20ajVxnY&list=PLuveNUf1W08ydYlF1hQ5TWvy5pZMorw1P](https://www.youtube.com/watch?v=GkD20ajVxnY&list=PLuveNUf1W08ydYlF1hQ5TWvy5pZMorw1P)
https://www.youtube.com/watch?v=HYYO2adk9fw&list=RDHYYO2adk9fw&start_radio=1
https://www.youtube.com/watch?v=iArXv64tCJA&list=RDiArXv64tCJA&start_radio=1https://www.youtube.com/watch?v=iArXv64tCJA&list=RDiArXv64tCJA&start_radio=1
https://www.youtube.com/watch?v=cHeDJ3nNx64&list=RDcHeDJ3nNx64&start_radio=1
https://www.youtube.com/watch?v=Vshg-hNUEjo&list=RDVshg-hNUEjo&start_radio=1
https://www.youtube.com/watch?v=qMXESlny4-I&list=RDEMfirC-sYS2rK49ZuNJqoj8Q&start_radio=1
https://www.youtube.com/watch?v=bx1Bh8ZvH84&list=PLMEZyDHJojxPndMRFPzCZ1T7RgzlHWBUb
https://www.youtube.com/watch?v=BFkTu8Y1KLs&list=PLxA687tYuMWj-FAqlC1aGULIgo9fjJOM7
https://www.youtube.com/watch?v=i6UtQTcG03A&list=PLR9LcjhNp2biDASle_Kwv_Hf6dWjmbwFg
https://www.youtube.com/watch?v=FGGo8LFmbjs&list=RDFGGo8LFmbjs&start_radio=1
https://www.youtube.com/watch?v=--eH76tgoNw&list=RD--eH76tgoNw&start_radio=1
https://www.youtube.com/watch?v=1G4isv_Fylg&list=PLzEfK9A1-zA8YVnCmfCUPGOXBUB97-Z9U
https://www.youtube.com/watch?v=QN1odfjtMoo&list=PLDtptmlbO0flwuYZJFisVQgp9MR8Yk4r-
https://www.youtube.com/watch?v=NsOK9XDE_MQ&list=PL5tfS0wGSIJe4rQpLITHxcK18DwQnOiu5
https://www.youtube.com/watch?v=kbpqZT_56Ns&list=PL14E2B03CA47801BA
"""

# Pause zwischen Downloads (Sekunden)
DELAY_SECONDS = 5


def extract_urls(raw_text: str) -> list[str]:
    """Extrahiert URLs robust aus Markdown, Plain-Text und verketteten URL-Zeilen."""
    matches = re.findall(r"https?://.*?(?=https?://|\s|\)|\]|$)", raw_text)
    seen: set[str] = set()
    ordered: list[str] = []
    for match in matches:
        url = match.strip().rstrip(",.;")
        if not url.startswith(("https://www.youtube.com/", "https://youtu.be/")):
            continue
        if url in seen:
            continue
        seen.add(url)
        ordered.append(url)
    return ordered


def resolve_media_tool_executable() -> str:
    media_tool_exe = Path(sys.executable).parent / "media-tool.exe"
    return str(media_tool_exe) if media_tool_exe.exists() else "media-tool"


def main() -> int:
    links = extract_urls(RAW_LINK_INPUT)
    if not links:
        print("Keine gültigen YouTube-URLs gefunden.")
        return 1

    media_tool_cmd = resolve_media_tool_executable()
    failures = 0

    for index, link in enumerate(links, start=1):
        print(f"\n[{index}/{len(links)}] Starte Download: {link}")
        command = [
            media_tool_cmd,
            "download",
            "series",
            link,
            "--format",
            "mp3",
            "--cookies-from-browser",
            "firefox",
        ]

        try:
            subprocess.run(command, check=True)
            print(f"Erfolgreich: {link}")
        except subprocess.CalledProcessError:
            failures += 1
            print(f"Fehler bei: {link}")

        time.sleep(DELAY_SECONDS)

    if failures:
        print(f"\nAbgeschlossen mit {failures} Fehler(n).")
        return 1

    print("\nAlle Downloads abgeschlossen.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
