#!/usr/bin/env python3
"""
Extract a Dropbox (or similar) zip into a destination directory.

Info-ZIP unzip on Linux often exits with code 2 on these archives due to
absolute path entries and filename encoding ("mapname: conversion of failed").
Python's zipfile handles UTF-8 / cp437 metadata and we normalize paths safely.
"""
from __future__ import annotations

import shutil
import sys
import zipfile
from pathlib import Path


def extract_zip(zip_path: str, dest_dir: str) -> None:
    dest = Path(dest_dir).resolve()
    last_error: Exception | None = None
    # Try metadata encodings Dropbox / Windows zips may use
    for enc in (None, "utf-8", "cp437"):
        if dest.exists():
            shutil.rmtree(dest)
        dest.mkdir(parents=True, exist_ok=True)
        kwargs = {}
        if enc is not None:
            kwargs["metadata_encoding"] = enc
        try:
            with zipfile.ZipFile(zip_path, "r", **kwargs) as zf:
                for info in zf.infolist():
                    name = info.filename.replace("\\", "/").lstrip("/")
                    if not name or name.endswith("/"):
                        continue
                    if ".." in Path(name).parts:
                        continue
                    out_path = (dest / name).resolve()
                    try:
                        out_path.relative_to(dest)
                    except ValueError:
                        continue
                    out_path.parent.mkdir(parents=True, exist_ok=True)
                    with zf.open(info) as src, open(out_path, "wb") as dst:
                        dst.write(src.read())
            return
        except (UnicodeDecodeError, zipfile.BadZipFile, OSError) as e:
            last_error = e
            continue

    raise RuntimeError(f"Could not extract zip: {last_error}") from last_error


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: extract-transcripts-zip.py ZIP DEST_DIR", file=sys.stderr)
        return 1
    try:
        extract_zip(sys.argv[1], sys.argv[2])
    except (OSError, zipfile.BadZipFile, RuntimeError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
