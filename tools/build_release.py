#!/usr/bin/env python3
"""
Build a Blender-installable zip for the bonsai_5d_plus addon.

Usage:
    python tools/build_release.py [--output DIR]

Output: dist/bonsai_5d_plus-X.Y.Z.zip

The zip contains a single top-level folder named 'bonsai_5d_plus/' so
Blender's addon installer can find __init__.py directly inside it.
"""

import argparse
import re
import zipfile
from pathlib import Path

ROOT    = Path(__file__).resolve().parent.parent
SRC_PKG = ROOT / "src" / "bonsai_5d_plus"
PKG_NAME = "bonsai_5d_plus"

_EXCLUDE_DIRS    = {"__pycache__"}
_EXCLUDE_SUFFIXES = {".pyc", ".pyo", ".pyd", ".zip"}


def _read_version() -> tuple[str, str, str]:
    text = (SRC_PKG / "__init__.py").read_text(encoding="utf-8")
    m = re.search(r'"version"\s*:\s*\((\d+)\s*,\s*(\d+)\s*,\s*(\d+)\)', text)
    if not m:
        raise ValueError("Could not parse 'version' tuple from __init__.py")
    return m.group(1), m.group(2), m.group(3)


def _should_exclude(rel: Path) -> bool:
    if any(part in _EXCLUDE_DIRS for part in rel.parts):
        return True
    return rel.suffix in _EXCLUDE_SUFFIXES


def build(output_dir: Path) -> Path:
    major, minor, patch = _read_version()
    zip_name = f"{PKG_NAME}-{major}.{minor}.{patch}.zip"
    output_dir.mkdir(parents=True, exist_ok=True)
    zip_path = output_dir / zip_name

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for file_path in sorted(SRC_PKG.rglob("*")):
            if not file_path.is_file():
                continue
            rel = file_path.relative_to(SRC_PKG)
            if _should_exclude(rel):
                continue
            arcname = Path(PKG_NAME) / rel
            zf.write(file_path, arcname)
            print(f"  + {arcname}")

    size_kb = zip_path.stat().st_size // 1024
    print(f"\nBuilt: {zip_path}  ({size_kb} KB)")
    return zip_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Build bonsai_5d_plus Blender addon zip")
    parser.add_argument(
        "--output", default=str(ROOT / "dist"),
        help="Output directory (default: dist/)",
    )
    args = parser.parse_args()
    build(Path(args.output))


if __name__ == "__main__":
    main()
