#!/usr/bin/env python3
"""Package the SaylientAI extension into dist/saylient-extension.zip.

The zip contains EXACTLY the shipped files listed in SHIPPED, in a
fixed order, with deterministic timestamps (1980-01-01) so repeated
builds are byte-identical. Tools, tests and dist/ itself are never
included. Run from anywhere:

    python3 apps/extension/tools/package.py
"""

from __future__ import annotations

import sys
import zipfile
from pathlib import Path

# Exactly the files Chrome loads (plus the README, for humans opening
# the zip). Nothing else ships.
SHIPPED = [
    "manifest.json",
    "sidepanel.html",
    "sidepanel.css",
    "sidepanel.js",
    "background.js",
    "content/extractor.js",
    "lib/redact.js",
    "lib/extract.js",
    "lib/util.js",
    "icons/icon16.png",
    "icons/icon48.png",
    "icons/icon128.png",
    "README.md",
]

FIXED_DATE = (1980, 1, 1, 0, 0, 0)


def main() -> int:
    ext_dir = Path(__file__).resolve().parent.parent  # apps/extension/
    dist_dir = ext_dir / "dist"
    dist_dir.mkdir(parents=True, exist_ok=True)
    out_path = dist_dir / "saylient-extension.zip"

    missing = [name for name in SHIPPED if not (ext_dir / name).is_file()]
    if missing:
        print(f"missing shipped files: {', '.join(missing)}", file=sys.stderr)
        return 1

    with zipfile.ZipFile(out_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for name in SHIPPED:
            data = (ext_dir / name).read_bytes()
            info = zipfile.ZipInfo(name, date_time=FIXED_DATE)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            zf.writestr(info, data)
    print(f"wrote {out_path} ({len(SHIPPED)} files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
