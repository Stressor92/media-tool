"""Utility to clean temporary test artifact files from project root."""

import logging
from pathlib import Path

ARTIFACTS = [
    "test_improve_audio.txt",
    "test_organize_audiobook.txt",
    "test_organize_audio.txt",
    "test_results.txt",
    "full_test_results.txt",
    "output.mkv",
]


def cleanup_root_artifacts(root: Path | str = "..") -> list[str]:  # default from tests/ path
    root_path = Path(root).resolve()

    deleted = []
    for filename in ARTIFACTS:
        candidate = root_path / filename
        if candidate.exists():
            candidate.unlink()
            deleted.append(str(candidate))

    return deleted


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logger = logging.getLogger(__name__)
    root_path = Path(__file__).resolve().parent.parent
    removed = cleanup_root_artifacts(root_path)
    if removed:
        logger.info("Removed test artifacts")
        for f in removed:
            logger.info("artifact_removed", extra={"context": {"path": f}})
    else:
        logger.info("No root test artifacts found")
