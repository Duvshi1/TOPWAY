#!/usr/bin/env python3
"""
publish_app.py - one-command TOPWAY catalog publisher.

Point it at an APK. It:
  1. reads package / versionCode / versionName / minSdk straight from the APK (aapt2),
  2. computes size + sha256,
  3. uploads the APK to the GitHub 'apps' release,
  4. adds or updates that package's entry in manifest.json (matched by package name),
  5. commits, pushes, and purges the jsDelivr cache so devices see it within minutes.

Usage:
    python publish_app.py <path-to-apk> [--name "Display Name"] [--category "מדיה"] [--icon icons/foo.png]

- If the package already exists in the manifest, its url/version/size/sha256 are updated in
  place and you don't need --name/--category (they're kept).
- For a brand-new app, you'll be prompted for a display name and category if not passed.

Nothing here is app-specific: it publishes whatever APK you give it. You decide what to publish.
"""
import argparse
import glob
import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.request

# ---- fixed project locations -------------------------------------------------
REPO      = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # C:\Topway\catalog
MANIFEST  = os.path.join(REPO, "manifest.json")
GH_OWNER  = "Duvshi1"
GH_REPO   = "TOPWAY"
GH_TAG    = "apps"                      # release that holds third-party app APKs
GH_RELEASE_ID = "369661797"
TOKEN_FILE = r"C:\ArcFox\provisioner\appprep\github.secret"
CDN_MANIFEST = "https://cdn.jsdelivr.net/gh/%s/%s@main/manifest.json" % (GH_OWNER, GH_REPO)
PURGE_URL    = "https://purge.jsdelivr.net/gh/%s/%s@main/manifest.json" % (GH_OWNER, GH_REPO)


def die(msg):
    print("ERROR: " + msg)
    sys.exit(1)


def find_aapt2():
    roots = [
        os.path.expandvars(r"%LOCALAPPDATA%\Android\Sdk\build-tools"),
        os.path.expandvars(r"%ANDROID_HOME%\build-tools"),
    ]
    cands = []
    for r in roots:
        cands += glob.glob(os.path.join(r, "*", "aapt2.exe"))
        cands += glob.glob(os.path.join(r, "*", "aapt2"))
    if not cands:
        die("aapt2 not found under Android SDK build-tools.")
    return sorted(cands)[-1]  # newest build-tools


def badging(aapt2, apk):
    out = subprocess.run([aapt2, "dump", "badging", apk],
                         capture_output=True, text=True, encoding="utf-8", errors="replace")
    if out.returncode != 0:
        die("aapt2 could not read the APK:\n" + (out.stderr or "")[:400])
    txt = out.stdout
    def grab(pattern):
        m = re.search(pattern, txt)
        return m.group(1) if m else None
    pkg = grab(r"package: name='([^']+)'")
    vcode = grab(r"versionCode='([^']+)'")
    vname = grab(r"versionName='([^']+)'")
    minsdk = grab(r"sdkVersion:'([^']+)'")
    label = grab(r"application-label:'([^']+)'")
    if not pkg or not vcode:
        die("APK is missing package name or versionCode.")
    return {
        "package": pkg,
        "versionCode": int(vcode),
        "versionName": vname,
        "minSdk": int(minsdk) if minsdk else None,
        "label": label,
    }


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


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
        # DELETE (and some other calls) return 204 No Content -- nothing to parse, and the
        # caller (delete_existing_asset) doesn't use a return value anyway.
        return json.loads(body) if body else None


def delete_existing_asset(asset_name):
    """A release can't hold two assets with the same name, so remove an old one first."""
    assets = gh_request("https://api.github.com/repos/%s/%s/releases/%s/assets"
                        % (GH_OWNER, GH_REPO, GH_RELEASE_ID))
    for a in assets:
        if a["name"] == asset_name:
            gh_request("https://api.github.com/repos/%s/%s/releases/assets/%d"
                       % (GH_OWNER, GH_REPO, a["id"]), method="DELETE")
            print("  removed old asset %s" % asset_name)


def upload_asset(apk, asset_name):
    """Upload first, delete second, rename third.

    A release can't hold two assets with the same name, which is why this used to delete
    before uploading -- but that leaves the live manifest pointing at a dead URL if the
    upload then fails, breaking that app for the whole fleet. Uploading under a temporary
    name first means every failure path leaves the OLD asset intact and still serving.
    """
    staging_name = asset_name + ".uploading"

    # A leftover staging asset from a previous interrupted run would collide; clear it.
    # This one IS safe to delete first -- nothing in the manifest ever points at it.
    delete_existing_asset(staging_name)

    url = "https://uploads.github.com/repos/%s/%s/releases/%s/assets?name=%s" \
          % (GH_OWNER, GH_REPO, GH_RELEASE_ID, staging_name)
    with open(apk, "rb") as f:
        data = f.read()
    res = gh_request(url, method="POST", data=data,
                     content_type="application/vnd.android.package-archive")
    asset_id = res["id"]

    # Confirm the published asset actually resolves before the manifest starts pointing at it.
    req = urllib.request.Request(res["browser_download_url"], method="HEAD")
    with urllib.request.urlopen(req) as r:
        if r.status != 200:
            die("published asset returned HTTP %d -- manifest NOT updated" % r.status)

    # Upload confirmed. Only now is it safe to remove the old asset and take its name.
    delete_existing_asset(asset_name)
    res = gh_request("https://api.github.com/repos/%s/%s/releases/assets/%d"
                     % (GH_OWNER, GH_REPO, asset_id),
                     method="PATCH",
                     data=json.dumps({"name": asset_name}).encode(),
                     content_type="application/json")
    return res["browser_download_url"]


def redact(cmd):
    """Never let a credential reach a log, whatever a future caller does."""
    tok = None
    try:
        tok = token()
    except Exception:
        pass
    out = []
    for a in cmd:
        if tok and tok in a:
            a = a.replace(tok, "***REDACTED***")
        out.append(re.sub(r"://[^/@\s]+:[^/@\s]+@", "://***:***@", a))
    return out


def run(cmd, cwd=None, env_extra=None):
    env = None
    if env_extra:
        env = os.environ.copy()
        env.update(env_extra)
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", env=env)
    if r.returncode != 0:
        die("command failed: %s\n%s\n%s" % (" ".join(redact(cmd)), r.stdout, r.stderr))
    return r.stdout.strip()


def main():
    ap = argparse.ArgumentParser(description="Publish an APK to the TOPWAY catalog.")
    ap.add_argument("apk", help="path to the .apk file")
    ap.add_argument("--name", help="display name (new apps only; kept for existing)")
    ap.add_argument("--category", help="category label, e.g. מדיה / ניווט / רדיו")
    ap.add_argument("--icon", help="icon path within the repo, e.g. icons/foo.png")
    ap.add_argument("--no-push", action="store_true", help="update manifest but don't commit/push")
    args = ap.parse_args()

    apk = os.path.abspath(args.apk)
    if not os.path.isfile(apk):
        die("no such file: " + apk)

    aapt2 = find_aapt2()
    info = badging(aapt2, apk)
    size = os.path.getsize(apk)
    sha = sha256_of(apk)
    asset_name = info["package"] + ".apk"

    print("Package     : %s" % info["package"])
    print("Version     : %s (%s)" % (info["versionName"], info["versionCode"]))
    print("Size        : %.1f MB" % (size / 1048576.0))
    print("sha256      : %s" % sha)

    with open(MANIFEST, encoding="utf-8") as f:
        manifest = json.load(f)
    apps = manifest["apps"]
    existing = next((a for a in apps if a.get("package") == info["package"]), None)

    if existing is None:
        name = args.name or input("Display name: ").strip()
        category = args.category or input("Category (blank = none): ").strip() or None
        if not name:
            die("a display name is required for a new app.")

    print("\nUploading to GitHub release '%s'..." % GH_TAG)
    url = upload_asset(apk, asset_name)
    print("  %s" % url)

    if existing is not None:
        existing["url"] = url
        existing["versionCode"] = info["versionCode"]
        if info["versionName"]:
            existing["versionName"] = info["versionName"]
        existing["size"] = size
        existing["sha256"] = sha
        if info["minSdk"]:
            existing["minSdk"] = info["minSdk"]
        existing.pop("store", None)  # a cloud APK is no longer a store redirect
        if args.category:
            existing["category"] = args.category
        if args.icon:
            existing["icon"] = args.icon
        action = "Updated"
    else:
        entry = {"name": name, "url": url, "package": info["package"],
                 "versionCode": info["versionCode"]}
        if info["versionName"]:
            entry["versionName"] = info["versionName"]
        entry["size"] = size
        entry["sha256"] = sha
        if info["minSdk"]:
            entry["minSdk"] = info["minSdk"]
        if args.icon:
            entry["icon"] = args.icon
        if category:
            entry["category"] = category
        apps.append(entry)
        action = "Added"

    with open(MANIFEST, "w", encoding="utf-8", newline="\n") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print("%s manifest entry for %s." % (action, info["package"]))

    if args.no_push:
        print("\n--no-push: manifest updated locally only. Commit when ready.")
        return

    print("\nCommitting and pushing...")
    run(["git", "add", "manifest.json"], cwd=REPO)
    run(["git", "commit", "-m",
         "%s %s %s (versionCode %d)" % (action, info["package"], info["versionName"], info["versionCode"])],
        cwd=REPO)
    # The token is passed via git's credential helper on stdin, never on the command line --
    # argv is visible in the process table and gets echoed by run()'s own error path.
    push_url = "https://github.com/%s/%s.git" % (GH_OWNER, GH_REPO)
    run(["git", "-c", "credential.helper=", "-c", "credential.helper=!f() { "
         "echo username=%s; echo password=$GH_TOKEN; }; f" % GH_OWNER,
         "push", push_url, "main"],
        cwd=REPO, env_extra={"GH_TOKEN": token()})

    print("Purging jsDelivr cache...")
    try:
        urllib.request.urlopen(PURGE_URL, timeout=20).read()
    except Exception as e:
        print("  (purge request failed, cache will refresh on its own: %s)" % e)

    print("\nDone. %s is live in the catalog." % info["package"])


if __name__ == "__main__":
    main()
