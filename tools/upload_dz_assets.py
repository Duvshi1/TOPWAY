#!/usr/bin/env python3
"""
upload_dz_assets.py - uploads a file to a dedicated "dz-assets" GitHub release on
Duvshi1/TOPWAY, separate from the "apps" release publish_app.py manages.

Why a separate release rather than reusing publish_app.py: that tool always writes an entry
into manifest.json, the customer-facing app-store list every fleet unit's MainActivity loads.
DZ's apps (Waze/Unicell Pango/AllFM Player) and boot logo are only ever installed through the
technician-only "Become DZ" action (DzMode.kt) -- they must never show up as installable options
for a random customer on some other platform. Same GitHub token/repo, deliberately different
release so the two purposes can never collide.

Usage:
    python upload_dz_assets.py <file> [<asset-name>]

Prints the browser_download_url and sha256 -- paste both into DzMode.kt's own asset list by hand
(a hardcoded list, same style as CanbusCatalog's resolved files, not a fetched manifest -- there
are only 4 of these and they change rarely, a dynamic manifest would be overhead for no benefit).
"""
import hashlib
import json
import os
import sys
import urllib.request

GH_OWNER = "Duvshi1"
GH_REPO = "TOPWAY"
GH_TAG = "dz-assets"
TOKEN_FILE = r"C:\ArcFox\provisioner\appprep\github.secret"


def die(msg):
    print("ERROR: " + msg)
    sys.exit(1)


def token():
    with open(TOKEN_FILE) as f:
        return f.read().strip()


def gh_request(url, method="GET", data=None, content_type=None):
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", "Bearer " + token())
    req.add_header("Accept", "application/vnd.github+json")
    if content_type:
        req.add_header("Content-Type", content_type)
    with urllib.request.urlopen(req) as r:
        body = r.read().decode()
        return json.loads(body) if body else None


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def get_or_create_release():
    try:
        return gh_request("https://api.github.com/repos/%s/%s/releases/tags/%s"
                          % (GH_OWNER, GH_REPO, GH_TAG))
    except urllib.error.HTTPError as e:
        if e.code != 404:
            raise
    print("Release '%s' doesn't exist yet -- creating it." % GH_TAG)
    return gh_request(
        "https://api.github.com/repos/%s/%s/releases" % (GH_OWNER, GH_REPO),
        method="POST",
        data=json.dumps({
            "tag_name": GH_TAG,
            "name": "DZ-only assets (technician tool, not the app store)",
            "body": "Assets for the \"Become DZ\" technician action (DzMode.kt). "
                    "Not customer-facing -- never referenced from manifest.json.",
            "draft": False,
            "prerelease": True,
        }).encode(),
        content_type="application/json",
    )


def delete_existing_asset(release_id, asset_name):
    assets = gh_request("https://api.github.com/repos/%s/%s/releases/%s/assets"
                        % (GH_OWNER, GH_REPO, release_id))
    for a in assets:
        if a["name"] == asset_name:
            gh_request("https://api.github.com/repos/%s/%s/releases/assets/%d"
                       % (GH_OWNER, GH_REPO, a["id"]), method="DELETE")
            print("  removed old asset %s" % asset_name)


def upload_asset(release_id, path, asset_name):
    delete_existing_asset(release_id, asset_name)
    url = "https://uploads.github.com/repos/%s/%s/releases/%s/assets?name=%s" \
          % (GH_OWNER, GH_REPO, release_id, asset_name)
    with open(path, "rb") as f:
        data = f.read()
    res = gh_request(url, method="POST", data=data,
                     content_type="application/octet-stream")
    return res["browser_download_url"]


def main():
    if len(sys.argv) < 2:
        die("usage: upload_dz_assets.py <file> [<asset-name>]")
    path = os.path.abspath(sys.argv[1])
    if not os.path.isfile(path):
        die("no such file: " + path)
    asset_name = sys.argv[2] if len(sys.argv) > 2 else os.path.basename(path)

    size = os.path.getsize(path)
    sha = sha256_of(path)
    print("File   : %s" % path)
    print("Size   : %.2f MB" % (size / 1048576.0))
    print("sha256 : %s" % sha)

    release = get_or_create_release()
    url = upload_asset(release["id"], path, asset_name)

    print("\nurl    : %s" % url)
    print("\nKotlin snippet:")
    print('    ResolvedFile(url = "%s", sha256 = "%s", size = %dL)' % (url, sha, size))


if __name__ == "__main__":
    main()
