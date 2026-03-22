"""
src/utils/video_hasher.py

OpenSubtitles hash calculation for video files.

Algorithm:
- Take first and last 64KB of file
- Add file size
- Calculate uint64 hash

This is MUCH faster than MD5/SHA (works on large files instantly)
"""

from __future__ import annotations

import struct
from pathlib import Path


class VideoHasher:
    """
    Calculate OpenSubtitles hash for video files

    Algorithm:
    1. Read first 64KB of file
    2. Read last 64KB of file
    3. Add file size
    4. Calculate uint64 hash with overflow

    This is MUCH faster than MD5/SHA (works on 50GB files in milliseconds)
    """

    @staticmethod
    def calculate_hash(file_path: Path) -> str:
        """
        Calculate OpenSubtitles hash for a video file.

        Returns 16-character hex string.

        Raises:
            ValueError if file < 128KB

        Example output: "8e245d9679d31e12"
        """
        longlongformat = '<q'  # little-endian long long
        bytesize = struct.calcsize(longlongformat)

        file_size = file_path.stat().st_size
        hash_value = file_size

        if file_size < 65536 * 2:
            raise ValueError(f"File too small for hash calculation: {file_size} bytes < 128KB")

        with open(file_path, 'rb') as f:
            # First 64KB
            for _ in range(65536 // bytesize):
                buffer = f.read(bytesize)
                if len(buffer) != bytesize:
                    break
                (l_value,) = struct.unpack(longlongformat, buffer)
                hash_value += l_value
                hash_value &= 0xFFFFFFFFFFFFFFFF  # uint64 overflow

            # Last 64KB
            f.seek(-65536, 2)  # Seek to end - 64KB
            for _ in range(65536 // bytesize):
                buffer = f.read(bytesize)
                if len(buffer) != bytesize:
                    break
                (l_value,) = struct.unpack(longlongformat, buffer)
                hash_value += l_value
                hash_value &= 0xFFFFFFFFFFFFFFFF

        return f"{hash_value:016x}"