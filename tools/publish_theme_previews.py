#!/usr/bin/env python3
"""
publish_theme_previews.py - extracts each theme APK's own bundled preview image
(icon_local_theme_details_public_01.*, the exact image dofun.variety's own theme-details
screen shows -- confirmed present under a slightly different res/ path and extension per
package, e.g. res/drawable-mdpi-v4/....jpg vs res/mipmap-mdpi-v4/....png) and uploads it as
a small standalone asset (theme-TW<N>-preview.<ext>), so the app's theme picker can show a
thumbnail without downloading the full multi-MB theme APK just to render a grid.

Reuses publish_theme_assets.py's exact upload mechanism.

Usage:
    python publish_theme_previews.py <path-to-apk> [<path-to-apk> ...]
"""
import os
import re
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from publish_theme_assets import upload_asset, die  # noqa: E402

PREVIEW_RE = re.compile(r"icon_local_theme_details_public_01\.(jpg|png)$", re.IGNORECASE)


def find_preview(apk_path):
    with zipfile.ZipFile(apk_path) as z:
        candidates = [n for n in z.namelist() if PREVIEW_RE.search(n)]
        if not candidates:
            return None, None
        # Prefer a plain (non "-port-") variant if more than one is present -- landscape is
        # this hardware's only real orientation (see topway-app-ui-redesign-2026-08), and a
        # "-port-" (portrait) resource dir is very unlikely to differ meaningfully for a
        # simple screenshot preview anyway, but keep the choice deterministic either way.
        candidates.sort(key=lambda n: ("-port-" in n, n))
        name = candidates[0]
        ext = PREVIEW_RE.search(name).group(1).lower()
        return z.read(name), ext


def main():
    if len(sys.argv) < 2:
        die("usage: publish_theme_previews.py <apk> [<apk> ...]")
    for path in sys.argv[1:]:
        if not os.path.isfile(path):
            print("SKIP (not found): %s" % path)
            continue
        base = os.path.splitext(os.path.basename(path))[0]  # "TW34"
        data, ext = find_preview(path)
        if data is None:
            print("SKIP (no preview image found): %s" % base)
            continue
        tmp_path = os.path.join(os.path.dirname(path), ".preview_%s.%s" % (base, ext))
        with open(tmp_path, "wb") as f:
            f.write(data)
        asset_name = "theme-%s-preview.%s" % (base, ext)
        print("Uploading %s (%d bytes)..." % (asset_name, len(data)))
        content_type = "image/jpeg" if ext == "jpg" else "image/png"
        url = upload_asset(tmp_path, asset_name, content_type=content_type)
        print("  -> %s" % url)
        os.remove(tmp_path)


if __name__ == "__main__":
    main()
