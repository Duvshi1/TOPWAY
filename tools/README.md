# Publishing apps to the TOPWAY catalog

One command adds (or updates) an app in the on-device store. It reads everything it needs
straight from the APK — you never edit `manifest.json` by hand.

## What it does

1. Reads package name, versionCode, versionName, minSdk from the APK (via `aapt2`).
2. Computes the file size and SHA-256.
3. Uploads the APK to the GitHub **`apps`** release.
4. Adds a new entry to `manifest.json`, or updates the existing one for that package.
5. Commits, pushes, and purges the jsDelivr cache.

Devices pick up the change within a few minutes (whenever they next open TOPWAY Tools).

## Prefer a window? (GUI)

```
python publish_gui.py
```

A small window: click **Browse…**, pick an APK, and its package/version/size are read for
you. For a new app, type a display name and pick a category; updating an existing app keeps
both. **Publish** uploads, updates the manifest, pushes, and purges the CDN with a live log.
Same engine as the command line, just clickable.

## Use it

**New app** (asks for a display name + category if you don't pass them):

```
python publish_app.py "C:\path\to\MyApp.apk" --name "My App" --category "מדיה"
```

**Update an app already in the catalog** — just point at the new APK; name/category are kept,
and the version/size/hash update automatically:

```
python publish_app.py "C:\path\to\MyApp-v2.apk"
```

**PowerShell wrapper** (same thing, friendlier):

```
.\Publish-App.ps1 "C:\path\to\MyApp.apk" -Name "My App" -Category "מדיה"
```

## Options

| Option | Meaning |
|--------|---------|
| `--name`     | Display name shown in the store (new apps only; kept on updates). |
| `--category` | Category label, e.g. `מדיה`, `ניווט`, `רדיו`, `בידור`. Used for the filter chips. |
| `--icon`     | Icon path inside the repo, e.g. `icons/myapp.png`. Optional — apps with no icon show a letter tile, installed apps show their real launcher icon. |
| `--no-push`  | Update `manifest.json` locally but don't commit/push. For reviewing before publishing. |

## Icons (optional)

Drop a PNG in `../icons/` (commit it), then pass `--icon icons/myapp.png`. Keep icons small
(square, ~192px). Not required.

## Notes

- **Only publish apps you have the right to distribute.** The tool is content-neutral — it
  publishes whatever APK you give it; deciding what may be hosted is on you.
- The catalog (`manifest.json` + this repo) is **public**. Anything published here is
  world-downloadable. Keep licensed/proprietary apps out of it unless you're certain your
  distribution rights cover public re-hosting.
- Requires: Python 3, Android SDK `build-tools` (for `aapt2`), and `git`. The GitHub token is
  read from a local file whose path is set by `TOKEN_FILE` in `publish_app.py` — whoever runs
  this tool already knows where their own token lives; that path isn't repeated here since this
  repo (and therefore this README) is public.
