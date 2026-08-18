#!/usr/bin/env python3
"""
publish_gui.py - a small window for publishing apps to the TOPWAY catalog.

Same engine as publish_app.py (it imports it), just with a UI: pick an APK, it reads the
package/version/size for you, you fill in a name + category for new apps, and Publish uploads
the APK, updates manifest.json, pushes, and purges the CDN — with a live log.

Run:  python publish_gui.py     (or double-click if .py is associated with Python)
Needs: Python 3 (tkinter ships with it), Android SDK build-tools, git.
"""
import os
import queue
import threading
import tkinter as tk
from tkinter import filedialog, ttk

import publish_app as engine


class Publisher(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("TOPWAY Catalog Publisher")
        self.geometry("640x600")
        self.minsize(560, 520)

        self.apk_path = tk.StringVar()
        self.name_var = tk.StringVar()
        self.category_var = tk.StringVar()
        self.icon_var = tk.StringVar()
        self.info = None            # parsed APK metadata
        self.existing = None        # matching manifest entry, if any
        self.log_q = queue.Queue()
        self.busy = False

        self._build()
        self.after(100, self._drain_log)

    # ---------------- UI ----------------
    def _build(self):
        pad = {"padx": 12, "pady": 6}
        root = ttk.Frame(self, padding=14)
        root.pack(fill="both", expand=True)

        ttk.Label(root, text="TOPWAY Catalog Publisher",
                  font=("Segoe UI", 15, "bold")).pack(anchor="w")
        ttk.Label(root, text="Pick an APK — its details are read for you. Fill a name + "
                             "category for new apps, then Publish.",
                  foreground="#666").pack(anchor="w", pady=(0, 10))

        # APK picker
        row = ttk.Frame(root); row.pack(fill="x", pady=(4, 2))
        ttk.Entry(row, textvariable=self.apk_path).pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="Browse…", command=self._browse).pack(side="left", padx=(8, 0))

        # Detected info card
        self.info_lbl = ttk.Label(root, text="No APK selected.", foreground="#333",
                                  font=("Consolas", 9), justify="left")
        self.info_lbl.pack(anchor="w", pady=(8, 8))

        form = ttk.Frame(root); form.pack(fill="x")
        ttk.Label(form, text="Display name").grid(row=0, column=0, sticky="w", **pad)
        self.name_entry = ttk.Entry(form, textvariable=self.name_var, width=40)
        self.name_entry.grid(row=0, column=1, sticky="ew", **pad)

        ttk.Label(form, text="Category").grid(row=1, column=0, sticky="w", **pad)
        self.cat_combo = ttk.Combobox(form, textvariable=self.category_var, width=37,
                                      values=self._known_categories())
        self.cat_combo.grid(row=1, column=1, sticky="ew", **pad)

        ttk.Label(form, text="Icon (optional)").grid(row=2, column=0, sticky="w", **pad)
        irow = ttk.Frame(form); irow.grid(row=2, column=1, sticky="ew", **pad)
        ttk.Entry(irow, textvariable=self.icon_var).pack(side="left", fill="x", expand=True)
        ttk.Button(irow, text="…", width=3, command=self._browse_icon).pack(side="left", padx=(6, 0))
        form.columnconfigure(1, weight=1)

        self.publish_btn = ttk.Button(root, text="Publish", command=self._publish, state="disabled")
        self.publish_btn.pack(anchor="e", pady=(6, 8))

        ttk.Label(root, text="Log", foreground="#666").pack(anchor="w")
        self.log = tk.Text(root, height=12, wrap="word", state="disabled",
                           background="#101010", foreground="#d7d2c8",
                           font=("Consolas", 9), relief="flat")
        self.log.pack(fill="both", expand=True, pady=(2, 0))

    def _known_categories(self):
        try:
            import json
            m = json.load(open(engine.MANIFEST, encoding="utf-8"))
            return sorted({a["category"] for a in m["apps"] if a.get("category")})
        except Exception:
            return []

    # ---------------- actions ----------------
    def _browse(self):
        p = filedialog.askopenfilename(title="Choose an APK",
                                       filetypes=[("Android app", "*.apk"), ("All files", "*.*")])
        if p:
            self.apk_path.set(p)
            self._read_apk(p)

    def _browse_icon(self):
        p = filedialog.askopenfilename(title="Choose an icon",
                                       filetypes=[("PNG image", "*.png"), ("All files", "*.*")])
        if p:
            self.icon_var.set(p)

    def _read_apk(self, path):
        self._log("Reading %s ..." % os.path.basename(path))
        try:
            aapt = engine.find_aapt2()
            info = engine.badging(aapt, path)
            size = os.path.getsize(path)
        except SystemExit:
            self.info_lbl.config(text="Could not read this APK.")
            self.publish_btn.config(state="disabled")
            return
        except Exception as e:
            self._log("Error: %s" % e)
            return

        self.info = info
        self.info["_size"] = size
        import json
        m = json.load(open(engine.MANIFEST, encoding="utf-8"))
        self.existing = next((a for a in m["apps"] if a.get("package") == info["package"]), None)

        status = "UPDATE existing entry" if self.existing else "NEW app"
        self.info_lbl.config(text=(
            "Package : %s\nVersion : %s (code %s)\nSize    : %.1f MB\nStatus  : %s"
            % (info["package"], info["versionName"], info["versionCode"],
               size / 1048576.0, status)))

        if self.existing:
            # keep the current name/category unless the user overrides
            self.name_var.set(self.existing.get("name", info["label"] or ""))
            self.category_var.set(self.existing.get("category", "") or "")
        else:
            self.name_var.set(info["label"] or "")

        self.publish_btn.config(state="normal")
        self._log("Ready. %s." % status)

    def _publish(self):
        if self.busy:
            return
        if not self.info:
            return
        if not self.name_var.get().strip():
            self._log("Please enter a display name.")
            return
        self.busy = True
        self.publish_btn.config(state="disabled")
        threading.Thread(target=self._publish_worker, daemon=True).start()

    def _publish_worker(self):
        try:
            import json
            apk = self.apk_path.get()
            info = self.info
            size = info["_size"]
            self._log("Computing SHA-256 ...")
            sha = engine.sha256_of(apk)
            asset = info["package"] + ".apk"

            self._log("Uploading %s to GitHub 'apps' release ..." % asset)
            url = engine.upload_asset(apk, asset)
            self._log("  " + url)

            m = json.load(open(engine.MANIFEST, encoding="utf-8"))
            entry = next((a for a in m["apps"] if a.get("package") == info["package"]), None)
            new = entry is None
            if new:
                entry = {"name": self.name_var.get().strip(), "package": info["package"]}
                m["apps"].append(entry)
            entry["name"] = self.name_var.get().strip()
            entry["url"] = url
            entry["versionCode"] = info["versionCode"]
            if info["versionName"]:
                entry["versionName"] = info["versionName"]
            entry["size"] = size
            entry["sha256"] = sha
            if info["minSdk"]:
                entry["minSdk"] = info["minSdk"]
            cat = self.category_var.get().strip()
            if cat:
                entry["category"] = cat
            icon = self.icon_var.get().strip()
            if icon:
                entry["icon"] = icon
            entry.pop("store", None)

            with open(engine.MANIFEST, "w", encoding="utf-8", newline="\n") as f:
                json.dump(m, f, ensure_ascii=False, indent=2)
                f.write("\n")
            self._log("%s manifest entry." % ("Added" if new else "Updated"))

            self._log("Committing and pushing ...")
            engine.run(["git", "add", "manifest.json"], cwd=engine.REPO)
            engine.run(["git", "commit", "-m",
                        "%s %s %s (versionCode %d)" % ("Add" if new else "Update",
                                                       info["package"], info["versionName"],
                                                       info["versionCode"])], cwd=engine.REPO)
            push = "https://%s:%s@github.com/%s/%s.git" % (
                engine.GH_OWNER, engine.token(), engine.GH_OWNER, engine.GH_REPO)
            engine.run(["git", "push", push, "main"], cwd=engine.REPO)

            self._log("Purging jsDelivr cache ...")
            try:
                import urllib.request
                urllib.request.urlopen(engine.PURGE_URL, timeout=20).read()
            except Exception as e:
                self._log("  (purge failed, refreshes on its own: %s)" % e)

            self._log("DONE — %s is live. Devices pick it up within a few minutes." % info["package"])
        except SystemExit as e:
            self._log("FAILED: %s" % e)
        except Exception as e:
            self._log("FAILED: %s" % e)
        finally:
            self.busy = False
            self.after(0, lambda: self.publish_btn.config(state="normal"))

    # ---------------- logging ----------------
    def _log(self, msg):
        self.log_q.put(msg)

    def _drain_log(self):
        try:
            while True:
                msg = self.log_q.get_nowait()
                self.log.config(state="normal")
                self.log.insert("end", msg + "\n")
                self.log.see("end")
                self.log.config(state="disabled")
        except queue.Empty:
            pass
        self.after(120, self._drain_log)


if __name__ == "__main__":
    Publisher().mainloop()
