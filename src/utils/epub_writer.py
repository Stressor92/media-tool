from __future__ import annotations

from pathlib import Path
import tempfile
from typing import Any
import xml.etree.ElementTree as ET
import zipfile


DC_NAMESPACE = "http://purl.org/dc/elements/1.1/"
OPF_NAMESPACE = "http://www.idpf.org/2007/opf"
XHTML_NAMESPACE = "http://www.w3.org/1999/xhtml"
EPUB_NAMESPACE = "http://www.idpf.org/2007/ops"

ET.register_namespace("dc", DC_NAMESPACE)
ET.register_namespace("opf", OPF_NAMESPACE)
ET.register_namespace("", XHTML_NAMESPACE)
ET.register_namespace("epub", EPUB_NAMESPACE)


class EpubWriteError(Exception):
    """Raised when writing back an EPUB fails."""


class EpubWriter:
    """Modify EPUB archives by updating OPF metadata and related assets."""

    def update_metadata(self, epub_path: Path, metadata: dict[str, str]) -> bool:
        """Update the OPF metadata fields for an EPUB file."""
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                self._extract_epub(epub_path, temp_path)
                opf_path = self._find_opf_file(temp_path)
                if opf_path is None:
                    return False
                self._update_opf_metadata(opf_path, metadata)
                self._pack_epub(temp_path, epub_path)
            return True
        except Exception as exc:
            raise EpubWriteError(f"Metadata update failed: {exc}") from exc

    def add_cover(self, epub_path: Path, cover_data: bytes) -> bool:
        """Add or replace a cover image and corresponding OPF references."""
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                self._extract_epub(epub_path, temp_path)
                opf_path = self._find_opf_file(temp_path)
                if opf_path is None:
                    return False
                opf_dir = opf_path.parent
                images_dir = opf_dir / "images"
                images_dir.mkdir(parents=True, exist_ok=True)
                cover_path = images_dir / "cover.jpg"
                cover_path.write_bytes(cover_data)
                self._add_cover_to_opf(opf_path, cover_href=self._relative_href(opf_dir, cover_path))
                self._pack_epub(temp_path, epub_path)
            return True
        except Exception as exc:
            raise EpubWriteError(f"Cover addition failed: {exc}") from exc

    def ensure_navigation(self, epub_path: Path) -> bool:
        """Ensure the EPUB contains a minimal nav.xhtml and manifest reference."""
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                self._extract_epub(epub_path, temp_path)
                opf_path = self._find_opf_file(temp_path)
                if opf_path is None:
                    return False
                tree = ET.parse(opf_path)
                root = tree.getroot()
                manifest = self._require_manifest(root)
                if self._manifest_has_nav(manifest):
                    self._write_tree(tree, opf_path)
                    self._pack_epub(temp_path, epub_path)
                    return True

                nav_path = opf_path.parent / "nav.xhtml"
                nav_path.write_text(self._build_nav_document(), encoding="utf-8")

                item = ET.SubElement(manifest, f"{{{OPF_NAMESPACE}}}item")
                item.set("id", "nav")
                item.set("href", self._relative_href(opf_path.parent, nav_path))
                item.set("media-type", "application/xhtml+xml")
                item.set("properties", "nav")

                spine = root.find(f".//{{{OPF_NAMESPACE}}}spine")
                if spine is not None and spine.find(f".//{{{OPF_NAMESPACE}}}itemref[@idref='nav']") is None:
                    itemref = ET.SubElement(spine, f"{{{OPF_NAMESPACE}}}itemref")
                    itemref.set("idref", "nav")
                    itemref.set("linear", "no")

                self._write_tree(tree, opf_path)
                self._pack_epub(temp_path, epub_path)
            return True
        except Exception as exc:
            raise EpubWriteError(f"Navigation generation failed: {exc}") from exc

    def _extract_epub(self, epub_path: Path, target_dir: Path) -> None:
        with zipfile.ZipFile(epub_path, "r") as epub:
            epub.extractall(target_dir)

    def _find_opf_file(self, epub_dir: Path) -> Path | None:
        try:
            container_path = epub_dir / "META-INF" / "container.xml"
            root = ET.parse(container_path).getroot()
            rootfile = root.find(".//{*}rootfile")
            if rootfile is not None:
                full_path = rootfile.get("full-path")
                if isinstance(full_path, str):
                    candidate = epub_dir / Path(full_path)
                    if candidate.exists():
                        return candidate
        except (FileNotFoundError, ET.ParseError):
            pass

        for opf_path in epub_dir.rglob("*.opf"):
            return opf_path
        return None

    def _update_opf_metadata(self, opf_path: Path, metadata: dict[str, str]) -> None:
        tree = ET.parse(opf_path)
        root = tree.getroot()
        metadata_elem = self._require_metadata(root)

        field_map = {
            "title": "title",
            "creator": "creator",
            "description": "description",
            "publisher": "publisher",
            "date": "date",
            "language": "language",
            "identifier": "identifier",
        }

        for field, value in metadata.items():
            tag_name = field_map.get(field, field)
            tag = f"{{{DC_NAMESPACE}}}{tag_name}"
            element = metadata_elem.find(tag)
            if element is None:
                element = ET.SubElement(metadata_elem, tag)
            element.text = value

        self._write_tree(tree, opf_path)

    def _add_cover_to_opf(self, opf_path: Path, cover_href: str) -> None:
        tree = ET.parse(opf_path)
        root = tree.getroot()
        manifest = self._require_manifest(root)
        metadata_elem = self._require_metadata(root)

        existing = manifest.find(f".//{{{OPF_NAMESPACE}}}item[@id='cover-image']")
        if existing is None:
            existing = ET.SubElement(manifest, f"{{{OPF_NAMESPACE}}}item")
            existing.set("id", "cover-image")
        existing.set("href", cover_href)
        existing.set("media-type", "image/jpeg")

        meta = metadata_elem.find(".//{*}meta[@name='cover']")
        if meta is None:
            meta = ET.SubElement(metadata_elem, f"{{{OPF_NAMESPACE}}}meta")
            meta.set("name", "cover")
        meta.set("content", "cover-image")

        self._write_tree(tree, opf_path)

    def _pack_epub(self, source_dir: Path, output_path: Path) -> None:
        with zipfile.ZipFile(output_path, "w") as epub:
            mimetype_path = source_dir / "mimetype"
            if mimetype_path.exists():
                epub.write(mimetype_path, "mimetype", compress_type=zipfile.ZIP_STORED)

            for file_path in sorted(source_dir.rglob("*")):
                if file_path.is_file() and file_path.name != "mimetype":
                    epub.write(file_path, file_path.relative_to(source_dir).as_posix(), compress_type=zipfile.ZIP_DEFLATED)

    @staticmethod
    def _relative_href(base_dir: Path, target_path: Path) -> str:
        return target_path.relative_to(base_dir).as_posix()

    @staticmethod
    def _build_nav_document() -> str:
        return (
            "<?xml version='1.0' encoding='utf-8'?>\n"
            "<html xmlns='http://www.w3.org/1999/xhtml' xmlns:epub='http://www.idpf.org/2007/ops'>\n"
            "  <head><title>Table of Contents</title></head>\n"
            "  <body>\n"
            "    <nav epub:type='toc' id='toc'>\n"
            "      <h1>Contents</h1>\n"
            "      <ol></ol>\n"
            "    </nav>\n"
            "  </body>\n"
            "</html>\n"
        )

    @staticmethod
    def _require_metadata(root: ET.Element) -> ET.Element:
        metadata_elem = root.find(f".//{{{OPF_NAMESPACE}}}metadata") or root.find(".//{*}metadata")
        if metadata_elem is None:
            raise EpubWriteError("OPF metadata section not found")
        return metadata_elem

    @staticmethod
    def _require_manifest(root: ET.Element) -> ET.Element:
        manifest = root.find(f".//{{{OPF_NAMESPACE}}}manifest") or root.find(".//{*}manifest")
        if manifest is None:
            raise EpubWriteError("OPF manifest section not found")
        return manifest

    @staticmethod
    def _manifest_has_nav(manifest: ET.Element) -> bool:
        for item in manifest.findall(".//{*}item"):
            properties = item.get("properties", "")
            if "nav" in properties.split():
                return True
        return False

    @staticmethod
    def _write_tree(tree: Any, opf_path: Path) -> None:
        tree.write(opf_path, encoding="utf-8", xml_declaration=True)