from __future__ import annotations

from pathlib import Path
import xml.etree.ElementTree as ET
import zipfile


class EpubReadError(Exception):
    """Raised when an EPUB cannot be parsed."""


class EpubReader:
    """Read metadata from EPUB container files."""

    def get_metadata(self, epub_path: Path) -> dict[str, str | None]:
        """Extract a small normalized metadata subset from one EPUB file."""
        try:
            with zipfile.ZipFile(epub_path, "r") as epub:
                opf_path = self._find_opf_file(epub)
                if opf_path is None:
                    return {}

                root = ET.fromstring(epub.read(opf_path))
                return self._parse_metadata(root)
        except Exception as exc:
            raise EpubReadError(f"Failed to read EPUB: {exc}") from exc

    def _find_opf_file(self, epub: zipfile.ZipFile) -> str | None:
        try:
            container = epub.read("META-INF/container.xml")
            root = ET.fromstring(container)
            namespace = {"container": "urn:oasis:names:tc:opendocument:xmlns:container"}
            rootfile = root.find(".//container:rootfile", namespace)
            if rootfile is not None:
                full_path = rootfile.get("full-path")
                if isinstance(full_path, str) and full_path:
                    return full_path
        except KeyError:
            pass

        for name in epub.namelist():
            if name.endswith(".opf"):
                return name
        return None

    def _parse_metadata(self, root: ET.Element) -> dict[str, str | None]:
        namespace = {"dc": "http://purl.org/dc/elements/1.1/"}
        metadata: dict[str, str | None] = {}

        mapping = {
            "title": ".//dc:title",
            "author": ".//dc:creator",
            "description": ".//dc:description",
            "identifier": ".//dc:identifier",
            "publisher": ".//dc:publisher",
            "date": ".//dc:date",
            "language": ".//dc:language",
        }

        for key, xpath in mapping.items():
            element = root.find(xpath, namespace)
            metadata[key] = element.text.strip() if element is not None and element.text else None

        return metadata