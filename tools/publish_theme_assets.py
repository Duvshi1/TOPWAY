#!/usr/bin/env python3
"""
publish_theme_assets.py - uploads TW<N>.apk theme packages to the existing 'apps' GitHub
release as raw assets, WITHOUT touching manifest.json -- themes aren't installable apps in
the catalog sense (see ThemeCatalog.kt on the app side), just files ThemeInstaller.kt
downloads on demand, the same way LauncherUiSwitch.kt already does for launcher-ui-*.zip.

Reuses publish_app.py's exact upload-then-rename safety pattern (upload under a temporary
name, confirm it resolves, only then replace any existing asset of the same name) and the
same GitHub PAT, so a failed upload never leaves the live asset URL broken mid-swap.

Usage:
    python publish_theme_assets.py <path-to-apk> [<path-to-apk> ...]
    python publish_theme_assets.py "C:\\Users\\PC\\Downloads\\Telegram Desktop\\TW*.apk"
"""
import glob
import hashlib
import json
import os
import sys
import urllib.request

GH_OWNER = "Duvshi1"
GH_REPO = "TOPWAY"
GH_RELEASE_ID = "369661797"
TOKEN_FILE = r"C:\ArcFox\provisioner\appprep\github.secret"


def die(msg):
    print("ERROR: " + msg)
    sys.exit(1)


def token():
    with open(TOKEN_FILE) as f:
        return f.read().strip()


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def gh_request(url, method="GET", data=None, content_type=None):
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", "Bearer " + token())
    req.add_header("Accept", "application/vnd.github+json")
    if content_type:
        req.add_header("Content-Type", content_type)
    with urllib.request.urlopen(req) as r:
        body = r.read().decode()
        return json.loads(body) if body else None


def delete_existing_asset(asset_name):
    assets = gh_request("https://api.github.com/repos/%s/%s/releases/%s/assets"
                         % (GH_OWNER, GH_REPO, GH_RELEASE_ID))
    for a in assets:
        if a["name"] == asset_name:
            gh_request("https://api.github.com/repos/%s/%s/releases/assets/%d"
                        % (GH_OWNER, GH_REPO, a["id"]), method="DELETE")
            print("  removed old asset %s" % asset_name)


def upload_asset(path, asset_name, content_type="application/vnd.android.package-archive"):
    staging_name = asset_name + ".uploading"
    delete_existing_asset(staging_name)

    url = "https://uploads.github.com/repos/%s/%s/releases/%s/assets?name=%s" \
          % (GH_OWNER, GH_REPO, GH_RELEASE_ID, staging_name)
    with open(path, "rb") as f:
        data = f.read()
    res = gh_request(url, method="POST", data=data, content_type=content_type)
    asset_id = res["id"]

    req = urllib.request.Request(res["browser_download_url"], method="HEAD")
    with urllib.request.urlopen(req) as r:
        if r.status != 200:
            die("published asset returned HTTP %d -- not renamed" % r.status)

    delete_existing_asset(asset_name)
    gh_request("https://api.github.com/repos/%s/%s/releases/assets/%d"
               % (GH_OWNER, GH_REPO, asset_id), method="PATCH",
               data=json.dumps({"name": asset_name}).encode(),
               content_type="application/json")
    final_url = "https://github.com/%s/%s/releases/download/apps/%s" \
                % (GH_OWNER, GH_REPO, asset_name)
    return final_url


def main():
    if len(sys.argv) < 2:
        die("usage: publish_theme_assets.py <apk> [<apk> ...]")
    paths = []
    for arg in sys.argv[1:]:
        matched = glob.glob(arg)
        paths += matched if matched else [arg]
    for path in paths:
        if not os.path.isfile(path):
            print("SKIP (not found): %s" % path)
            continue
        base = os.path.splitext(os.path.basename(path))[0]  # "TW34"
        asset_name = "theme-%s.apk" % base
        size = os.path.getsize(path)
        digest = sha256(path)
        print("Uploading %s (%d bytes, sha256=%s)..." % (asset_name, size, digest))
        url = upload_asset(path, asset_name)
        print("  -> %s" % url)
        print("  size=%d sha256=%s" % (size, digest))


if __name__ == "__main__":
    main()
