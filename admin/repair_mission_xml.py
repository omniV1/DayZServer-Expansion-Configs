#!/usr/bin/env python3
"""Repair common XML packaging issues in downloaded third-party mission files."""
from __future__ import annotations

import argparse
import re
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

COMMENT_RE = re.compile(r"<!--.*?-->", re.S)
XML_DECL_RE = re.compile(r"<\?xml[^>]*\?>", re.I)


def strip_comments(text: str) -> str:
    return COMMENT_RE.sub("", text)


def split_xml_documents(text: str) -> list[str]:
    starts = [match.start() for match in XML_DECL_RE.finditer(text)]
    if len(starts) <= 1:
        return [text]
    starts.append(len(text))
    return [text[starts[i] : starts[i + 1]].strip() for i in range(len(starts) - 1)]


def merge_documents(parts: list[str], path: Path) -> ET.ElementTree:
    roots = []
    for part in parts:
        if not part:
            continue
        roots.append(ET.fromstring(part))
    if not roots:
        raise ValueError(f"No XML documents found in {path}")

    root = roots[0]
    for other in roots[1:]:
        if other.tag != root.tag:
            raise ValueError(f"Cannot merge {path}: root {root.tag!r} != {other.tag!r}")
        root.extend(list(other))
    return ET.ElementTree(root)


def repair_file(path: Path) -> bool:
    original = path.read_text(encoding="utf-8-sig", errors="replace")
    cleaned = strip_comments(original)
    parts = split_xml_documents(cleaned)

    try:
        tree = merge_documents(parts, path)
    except Exception:
        ET.fromstring(cleaned)
        merged = cleaned
    else:
        ET.indent(tree, space="    ")
        root = tree.getroot()
        merged = ET.tostring(root, encoding="unicode")
        merged = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n' + merged + "\n"

    if merged != original:
        path.write_text(merged, encoding="utf-8")
        return True
    return False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("missions", nargs="+", help="Mission folder names under mpmissions/")
    args = parser.parse_args()

    changed = []
    for mission in args.missions:
        root = ROOT / "mpmissions" / mission
        if not root.is_dir():
            raise FileNotFoundError(root)
        for path in sorted(root.rglob("*.xml")):
            try:
                ET.parse(path)
                continue
            except Exception:
                pass
            if repair_file(path):
                changed.append(path.relative_to(ROOT))
            ET.parse(path)

    if changed:
        print("Repaired XML files:")
        for path in changed:
            print(f"  - {path}")
    else:
        print("No XML repairs needed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
