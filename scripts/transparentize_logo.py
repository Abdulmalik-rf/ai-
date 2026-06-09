"""Process the source Logo.png into the public web assets.

Generates three files:
  - apps/web/public/logo.png       — full logo, transparent bg
  - apps/web/public/logo-mark.png  — icon-only (speech-bubble), tightly cropped
  - apps/web/public/favicon.png    — 256x256 thumbnail of the icon-only mark

The icon/wordmark split is found automatically by scanning for a horizontal
band of fully-transparent rows between the two ink regions.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "Logo.png"
PUBLIC = ROOT / "apps" / "web" / "public"
OUT_LOGO = PUBLIC / "logo.png"
OUT_MARK = PUBLIC / "logo-mark.png"
OUT_FAVICON = PUBLIC / "favicon.png"

# Pixels brighter than this on every channel become transparent.
BG_THRESHOLD = 240


def transparentize(img: Image.Image) -> Image.Image:
    """Replace near-white background with alpha=0."""
    img = img.convert("RGBA")
    pixels = img.load()
    w, h = img.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = pixels[x, y]
            if r >= BG_THRESHOLD and g >= BG_THRESHOLD and b >= BG_THRESHOLD:
                pixels[x, y] = (r, g, b, 0)
    return img


def row_has_ink(img: Image.Image, y: int, alpha_min: int = 32) -> bool:
    """True if any pixel on row y has alpha >= alpha_min."""
    w = img.width
    pixels = img.load()
    for x in range(w):
        if pixels[x, y][3] >= alpha_min:
            return True
    return False


def find_icon_bbox(img: Image.Image) -> tuple[int, int, int, int]:
    """Return (left, top, right, bottom) of the icon region.

    Strategy: walk rows top-to-bottom. The first run of inked rows is the icon.
    Stop at the first significant transparent gap below it. Then snap left/right
    to the bounding box of inked pixels within that vertical band.
    """
    w, h = img.size

    # Walk down to find the first inked row (top of icon).
    top = 0
    while top < h and not row_has_ink(img, top):
        top += 1

    # Walk down through the icon ink, then through any transparent gap, until
    # we hit ink again — that's the wordmark. The "bottom of icon" is the start
    # of the gap.
    in_ink = True
    gap_start = top
    bottom = top
    GAP_TOLERANCE_PX = 8  # tiny gaps inside icon are OK

    y = top
    while y < h:
        ink = row_has_ink(img, y)
        if in_ink:
            if not ink:
                # might be a gap — check ahead
                lookahead = 0
                while y + lookahead < h and not row_has_ink(img, y + lookahead):
                    lookahead += 1
                if lookahead > GAP_TOLERANCE_PX:
                    # significant gap → end of icon
                    bottom = y
                    break
                else:
                    bottom = y + lookahead
                    y += lookahead
                    continue
            else:
                bottom = y
        y += 1
    else:
        bottom = h - 1

    # Now horizontal bbox within (top..bottom)
    pixels = img.load()
    left = w
    right = 0
    for yy in range(top, bottom + 1):
        for xx in range(w):
            if pixels[xx, yy][3] >= 32:
                if xx < left:
                    left = xx
                if xx > right:
                    right = xx

    # Pad a touch so strokes aren't clipped at the edge
    pad = max(2, (right - left) // 30)
    left = max(0, left - pad)
    right = min(w - 1, right + pad)
    top = max(0, top - pad)
    bottom = min(h - 1, bottom + pad)
    return left, top, right + 1, bottom + 1


def square_pad(img: Image.Image) -> Image.Image:
    """Pad the image so it becomes a perfect square (transparent padding)."""
    w, h = img.size
    side = max(w, h)
    out = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    out.paste(img, ((side - w) // 2, (side - h) // 2))
    return out


def main() -> None:
    if not SRC.exists():
        raise SystemExit(f"Source logo not found at {SRC}")

    print("loading", SRC)
    full = transparentize(Image.open(SRC))

    # 1) Full transparent logo (icon + wordmark together, square)
    OUT_LOGO.parent.mkdir(parents=True, exist_ok=True)
    full.save(OUT_LOGO, "PNG", optimize=True)
    print(f"wrote {OUT_LOGO.relative_to(ROOT)}  {full.size}  ({OUT_LOGO.stat().st_size:,} B)")

    # 2) Icon-only mark
    bbox = find_icon_bbox(full)
    print(f"detected icon bbox: {bbox}")
    icon = full.crop(bbox)
    icon = square_pad(icon)
    icon.save(OUT_MARK, "PNG", optimize=True)
    print(f"wrote {OUT_MARK.relative_to(ROOT)}  {icon.size}  ({OUT_MARK.stat().st_size:,} B)")

    # 3) Favicon — 256x256 thumbnail of the mark
    fav = icon.copy()
    fav.thumbnail((256, 256), Image.LANCZOS)
    fav.save(OUT_FAVICON, "PNG", optimize=True)
    print(f"wrote {OUT_FAVICON.relative_to(ROOT)}  {fav.size}  ({OUT_FAVICON.stat().st_size:,} B)")


if __name__ == "__main__":
    main()
