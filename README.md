# TOPWAY Catalog

Catalog for the TOPWAY Tools on-device app store (`com.uzeb.topway.tools`), running on TOPWAY TS18
head units. Served through jsDelivr in front of this repo:

```
https://cdn.jsdelivr.net/gh/Duvshi1/TOPWAY@main/manifest.json
```

APK binaries live in [GitHub Releases](../../releases) of this repo (jsDelivr has a ~20MB cap that
most APKs exceed; Releases are served through Fastly with no such limit).

## manifest.json schema

```json
{
  "apps": [
    {
      "name": "RustDesk",
      "url": "https://github.com/Duvshi1/TOPWAY/releases/download/apps/RustDesk-uzeb.apk",
      "package": "com.carriez.flutter_hbb",
      "versionCode": 1,
      "versionName": "1.0",
      "size": 41943040,
      "sha256": "…",
      "icon": "icons/rustdesk.png",
      "category": "תמיכה מרחוק",
      "notes": "..."
    }
  ]
}
```

| field         | required | notes                                                                 |
|---------------|----------|------------------------------------------------------------------------|
| `name`        | yes      | display name                                                          |
| `url`         | yes      | direct APK download URL (GitHub Release asset)                        |
| `package`     | no       | Android package id — used to detect "installed" state                |
| `versionCode` | no       | for update checks                                                     |
| `versionName` | no       | shown in the UI                                                       |
| `size`        | no       | bytes — used for a progress bar and download-integrity length check   |
| `sha256`      | no       | lowercase hex — verified after download; falls back to a ZIP-magic check if absent |
| `icon`        | no       | relative path under `icons/` in this repo, or an absolute URL         |
| `category`    | no       | free text, shown as a UI tag                                          |
| `notes`       | no       | free text                                                             |

## Publishing an app

1. Upload the APK to a [Release](../../releases) of this repo (any tag, e.g. `apps`).
2. Add an entry to `manifest.json` pointing at the release asset's `browser_download_url`.
3. Push to `main`. jsDelivr caches `@main` for ~12h — force a refresh with:
   `https://purge.jsdelivr.net/gh/Duvshi1/TOPWAY@main/manifest.json`
