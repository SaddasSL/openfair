"""Draw numbered inspection balloons on each page image."""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

RADIUS = 28
COLOR = (200, 0, 0)
FONTS = ["arialbd.ttf", "C:/Windows/Fonts/arialbd.ttf", "DejaVuSans-Bold.ttf",
         "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/Library/Fonts/Arial Bold.ttf"]


def is_ballooned(entry: dict) -> bool:
    """Datum symbols, plain notes and reference/basic dimensions get no balloon."""
    if entry.get("type") == "note":
        return False
    if entry.get("reference") or entry.get("basic"):
        return False
    return True


def load_font(size: int):
    for f in FONTS:
        try:
            return ImageFont.truetype(f, size)
        except OSError:
            continue
    return ImageFont.load_default()


def number_entries(entries: list[dict]) -> int:
    """Assign balloon numbers in page order. Returns how many were numbered."""
    n = 0
    for e in entries:
        if is_ballooned(e):
            n += 1
            e["balloon"] = n
        else:
            e.pop("balloon", None)
    return n


def draw_page(image_path: str, entries: list[dict], out_path: str | Path) -> Path:
    """Draw balloons for the entries that belong to this page image."""
    img = Image.open(image_path).convert("RGB")
    draw = ImageDraw.Draw(img)
    font = load_font(int(RADIUS * 1.0))
    groups = defaultdict(list)
    for e in entries:
        if e.get("balloon") and e.get("bbox"):
            groups[tuple(e["bbox"])].append(e)
    boxes = [tuple(b) for b in groups]          # callout text that balloons must not cover
    placed: list[tuple[float, float]] = []
    gap = RADIUS + 10

    def free(cx, cy):
        if not (RADIUS <= cx <= img.width - RADIUS and RADIUS <= cy <= img.height - RADIUS):
            return False
        if any(abs(cx - px) < 2 * RADIUS + 4 and abs(cy - py) < 2 * RADIUS + 4 for px, py in placed):
            return False
        return not any(bx - RADIUS < cx < bx + bw + RADIUS and by - RADIUS < cy < by + bh + RADIUS
                       for bx, by, bw, bh in boxes)

    for bbox, members in groups.items():
        x, y, bw, bh = bbox
        mid = y + bh / 2
        for e in members:
            # try left, above, right, below, then step further out
            spots = []
            for k in range(1, 6):
                d = gap + (k - 1) * (2 * RADIUS + 6)
                spots += [(x - d, mid), (x + bw / 2, y - d), (x + bw + d, mid), (x + bw / 2, y + bh + d)]
            cx, cy = next((p for p in spots if free(*p)), spots[0])
            cx = min(max(RADIUS, cx), img.width - RADIUS)
            cy = min(max(RADIUS, cy), img.height - RADIUS)
            placed.append((cx, cy))
            # leader from the balloon edge to the nearest point of the callout box
            tx, ty = min(max(cx, x), x + bw), min(max(cy, y), y + bh)
            dx, dy = tx - cx, ty - cy
            d = max(1.0, (dx * dx + dy * dy) ** 0.5)
            if d > RADIUS:
                draw.line((cx + dx / d * RADIUS, cy + dy / d * RADIUS, tx, ty), fill=COLOR, width=3)
            draw.ellipse((cx - RADIUS, cy - RADIUS, cx + RADIUS, cy + RADIUS),
                         outline=COLOR, width=4, fill=(255, 255, 255))
            draw.text((cx, cy), str(e["balloon"]), fill=COLOR, font=font, anchor="mm")
    out = Path(out_path)
    img.save(out)
    return out


def save_pdf(images: list[Path], out_path: str | Path, dpi: int = 300) -> Path:
    """Combine ballooned page images into one PDF."""
    pages = [Image.open(p).convert("RGB") for p in images]
    out = Path(out_path)
    pages[0].save(out, save_all=True, append_images=pages[1:], resolution=dpi)
    return out
