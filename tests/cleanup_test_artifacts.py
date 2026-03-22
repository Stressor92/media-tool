"""Utility to clean temporary test artifact files from project root."""

from pathlib import Path

ARTIFACTS = [
    "test_improve_audio.txt",
    "test_organize_audiobook.txt",
    "test_organize_audio.txt",
    "test_results.txt",
    "full_test_results.txt",
    "output.mkv",
]


def cleanup_root_artifacts(root: Path | str = ".."):  # default from tests/ path
    root_path = Path(root).resolve()

    deleted = []
    for filename in ARTIFACTS:
        candidate = root_path / filename
        if candidate.exists():
            candidate.unlink()
            deleted.append(str(candidate))

    return deleted


if __name__ == "__main__":
    root_path = Path(__file__).resolve().parent.parent
    removed = cleanup_root_artifacts(root_path)
    if removed:
        print("Removed test artifacts:")
        for f in removed:
            print(f" - {f}")
    else:
        print("No root test artifacts found.")
