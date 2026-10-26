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


def _page_masks(img: Image.Image):
    """Callout ink (annotation pixels, without large part geometry) and blank paper."""
    import cv2
    import numpy as np
    from src.ballooning.locate import MAX_CLUSTER_FRAC, annotation_mask
    bgr = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
    ink, _ = annotation_mask(bgr)
    n, labels, stats, _ = cv2.connectedComponentsWithStats(ink)
    big = [i for i in range(1, n) if stats[i, cv2.CC_STAT_AREA] > MAX_CLUSTER_FRAC * ink.size / 4]
    if big:
        ink[np.isin(labels, big)] = 0
    blank = (bgr.min(axis=2) > 225).astype(np.uint8)
    used = (1 - blank).astype(np.uint8)
    integral = cv2.integral(used)
    return ink > 0, integral


def _ink_near(ink, bbox):
    """Coordinates of callout ink inside the box, as (ys, xs)."""
    import numpy as np
    x, y, w, h = (int(v) for v in bbox)
    ys, xs = np.nonzero(ink[max(0, y):y + h, max(0, x):x + w])
    return ys + max(0, y), xs + max(0, x)


def _best_spot(bbox, ink, integral, placed, size, estimate=None):
    """Blank spot closest to the callout's own ink, so the balloon sits right beside it.

    When one ink group holds several callouts, the model's own position estimate
    picks the part of the group that belongs to this callout.
    """
    import numpy as np
    W, H = size
    ys, xs = _ink_near(ink, bbox)
    if len(xs) == 0:
        return None
    if estimate and len(estimate) == 4 and tuple(estimate) != tuple(bbox):
        ex, ey, ew, eh = estimate
        mx, my = max(ew, 2 * RADIUS) * 0.25, max(eh, 2 * RADIUS) * 0.25
        inside = (xs >= ex - mx) & (xs <= ex + ew + mx) & (ys >= ey - my) & (ys <= ey + eh + my)
        if inside.sum() >= 50:
            ys, xs = ys[inside], xs[inside]
    if len(xs) > 4000:  # thin out for speed; shape is preserved
        step = len(xs) // 4000 + 1
        ys, xs = ys[::step], xs[::step]
    x, y, w, h = bbox
    reach = 4 * RADIUS
    gx = np.arange(max(RADIUS, x - reach), min(W - RADIUS, x + w + reach), 10)
    gy = np.arange(max(RADIUS, y - reach), min(H - RADIUS, y + h + reach), 10)
    if not len(gx) or not len(gy):
        return None
    cx, cy = np.meshgrid(gx, gy)
    cx, cy = cx.ravel(), cy.ravel()
    r = RADIUS + 8
    x0, y0, x1, y1 = cx - r, cy - r, cx + r, cy + r
    filled = integral[y1, x1] - integral[y0, x1] - integral[y1, x0] + integral[y0, x0]
    ok = filled <= 0.002 * (2 * r) ** 2
    for px, py in placed:
        ok &= (np.abs(cx - px) >= 2 * RADIUS + 6) | (np.abs(cy - py) >= 2 * RADIUS + 6)
    if not ok.any():
        return None
    cx, cy = cx[ok], cy[ok]
    # distance from each candidate to the nearest ink pixel of this callout
    d = np.full(len(cx), np.inf)
    for i in range(0, len(xs), 500):
        dx = cx[:, None] - xs[None, i:i + 500]
        dy = cy[:, None] - ys[None, i:i + 500]
        d = np.minimum(d, np.sqrt(dx * dx + dy * dy).min(axis=1))
    k = int(np.argmin(d))
    j = int(np.argmin((xs - cx[k]) ** 2 + (ys - cy[k]) ** 2))
    return float(cx[k]), float(cy[k]), float(xs[j]), float(ys[j])


def draw_page(image_path: str, entries: list[dict], out_path: str | Path) -> Path:
    """Draw balloons for the entries that belong to this page image."""
    img = Image.open(image_path).convert("RGB")
    try:
        ink, integral = _page_masks(img)
    except Exception:  # placement helpers are optional; fall back to box edges
        ink = integral = None
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
            spot = (_best_spot(bbox, ink, integral, placed, img.size, e.get("bbox_estimate"))
                    if ink is not None else None)
            if spot:
                cx, cy, tx, ty = spot
            else:
                # try left, above, right, below, then step further out
                spots = []
                for k in range(1, 6):
                    d = gap + (k - 1) * (2 * RADIUS + 6)
                    spots += [(x - d, mid), (x + bw / 2, y - d), (x + bw + d, mid), (x + bw / 2, y + bh + d)]
                cx, cy = next((p for p in spots if free(*p)), spots[0])
                cx = min(max(RADIUS, cx), img.width - RADIUS)
                cy = min(max(RADIUS, cy), img.height - RADIUS)
                tx, ty = min(max(cx, x), x + bw), min(max(cy, y), y + bh)
            placed.append((cx, cy))
            # leader from the balloon edge to the callout
            dx, dy = tx - cx, ty - cy
            d = max(1.0, (dx * dx + dy * dy) ** 0.5)
            if d > RADIUS + 12:
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
