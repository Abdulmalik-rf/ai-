"""Download every file in a public Google Drive folder.

`gdown --folder` truncates large public folders silently and the per-file
gdown CLI fails with "Cannot retrieve the public link" once Drive's anti-abuse
heuristic kicks in. This script avoids both: it scrapes
`embeddedfolderview` (no auth) for the (id, name) list, then downloads each
via the `drive.usercontent.google.com/download?confirm=t` endpoint that
bypasses the virus-scan warning page.

Resumable: skips files already present in the output dir (NFC-normalized
filename match — Windows often stores Arabic in NFD).
"""
from __future__ import annotations

import argparse
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "drive_raw"

EMBED_URL = "https://drive.google.com/embeddedfolderview?id={folder_id}#list"
DL_URL = "https://drive.usercontent.google.com/download?id={file_id}&export=download&authuser=0&confirm=t"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"


def fetch_listing(folder_id: str) -> list[tuple[str, str]]:
    url = EMBED_URL.format(folder_id=folder_id)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        html = r.read().decode("utf-8", errors="replace")
    pattern = re.compile(
        r'href="https://drive\.google\.com/file/d/([A-Za-z0-9_-]{20,})/[^"]*"[^>]*>'
        r'.*?class="flip-entry-title"[^>]*>([^<]+)</div>',
        re.DOTALL,
    )
    out: list[tuple[str, str]] = []
    for m in pattern.finditer(html):
        fid, name = m.group(1), m.group(2).strip()
        for ent, repl in (("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"),
                          ("&quot;", '"'), ("&#39;", "'")):
            name = name.replace(ent, repl)
        out.append((fid, name))
    seen: dict[str, str] = {}
    for fid, n in out:
        seen.setdefault(fid, n)
    return list(seen.items())


def safe_filename(name: str) -> str:
    name = unicodedata.normalize("NFC", name)
    name = re.sub(r'[\\/:*?"<>|]', "-", name)
    name = re.sub(r"\s+", " ", name).strip(" .")
    if not name:
        name = "untitled"
    return name


def find_existing(out_dir: Path, target_name: str) -> Path | None:
    if not out_dir.exists():
        return None
    target_nfc = unicodedata.normalize("NFC", target_name)
    for p in out_dir.iterdir():
        if p.is_file() and unicodedata.normalize("NFC", p.name) == target_nfc:
            return p
    return None


def http_download(file_id: str, target: Path) -> tuple[bool, str]:
    target.parent.mkdir(parents=True, exist_ok=True)
    url = DL_URL.format(file_id=file_id)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            ct = r.headers.get("Content-Type", "")
            if "text/html" in ct:
                # Drive sometimes returns an HTML interstitial — peek for a
                # uuid the page uses to confirm large-file downloads.
                page = r.read(4096).decode("utf-8", errors="replace")
                m = re.search(r'name="uuid" value="([0-9a-f-]+)"', page)
                if not m:
                    return False, f"interstitial without uuid (CT={ct})"
                form_url = url + f"&uuid={m.group(1)}"
                req2 = urllib.request.Request(form_url, headers={"User-Agent": UA})
                with urllib.request.urlopen(req2, timeout=120) as r2:
                    data = r2.read()
            else:
                data = r.read()
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as e:
        return False, repr(e)
    if len(data) < 1024:
        return False, f"too small ({len(data)} bytes)"
    target.write_bytes(data)
    return True, "ok"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--folder-id", default="19SJoYlaBVomrqlmXGlkWoN9_8XBAKWKn")
    parser.add_argument("--out-dir", type=Path, default=RAW)
    parser.add_argument("--list-only", action="store_true")
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--delay", type=float, default=0.4,
                        help="Sleep between downloads (seconds).")
    args = parser.parse_args()

    print(f"Fetching listing for folder {args.folder_id} …", flush=True)
    entries = fetch_listing(args.folder_id)
    print(f"Found {len(entries)} unique files.\n", flush=True)
    if args.list_only:
        for fid, n in entries:
            print(f"  {fid}  {n}")
        return

    name_counts: dict[str, int] = {}
    for _, n in entries:
        sn = safe_filename(n)
        if not sn.lower().endswith(".pdf"):
            sn += ".pdf"
        name_counts[sn] = name_counts.get(sn, 0) + 1

    placements: list[tuple[str, Path]] = []
    used: set[str] = set()
    for fid, n in entries:
        sn = safe_filename(n)
        if not sn.lower().endswith(".pdf"):
            sn += ".pdf"
        if name_counts[sn] > 1:
            sn = f"{Path(sn).stem} ({fid[:8]}).pdf"
        suffix = 0
        original = sn
        while sn in used:
            suffix += 1
            sn = f"{Path(original).stem} ({suffix}){Path(original).suffix}"
        used.add(sn)
        placements.append((fid, args.out_dir / sn))

    print("=== Downloading ===", flush=True)
    ok = 0
    fail: list[tuple[str, Path, str]] = []
    for i, (fid, dst) in enumerate(placements, 1):
        existing = find_existing(dst.parent, dst.name)
        if existing is not None and existing.stat().st_size > 1024:
            ok += 1
            if i % 20 == 0:
                print(f"  [{i}/{len(placements)}] ok so far: {ok}", flush=True)
            continue
        last_err = ""
        for attempt in range(1, args.retries + 1):
            success, msg = http_download(fid, dst)
            if success:
                ok += 1
                print(f"  [{i}/{len(placements)}] {dst.name}  ({dst.stat().st_size//1024} KB)", flush=True)
                break
            last_err = msg
            time.sleep(2 * attempt)
        else:
            fail.append((fid, dst, last_err))
            print(f"  [{i}/{len(placements)}] FAIL {dst.name}: {last_err[:120]}", flush=True)
        time.sleep(args.delay)

    print(f"\nDone. {ok}/{len(placements)} downloaded.", flush=True)
    if fail:
        print("\nFailures:")
        for fid, dst, err in fail:
            print(f"  - {dst.name}  (id={fid}) -- {err[:120]}")
        sys.exit(1)


if __name__ == "__main__":
    main()
