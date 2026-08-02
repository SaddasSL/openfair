"""Diagnostic: extract from a tight full-res crop of the bottom-right callout."""
from pathlib import Path

from PIL import Image

from src.extraction.extract import extract

SRC = "output/nist_ctc3_page1.png"
CROP = (2100, 1400, 3300, 2400)  # right/bottom region with the B-datum hole callouts

img = Image.open(SRC).crop(CROP)
p = Path("output/diag_bottomright.png")
img.save(p)
print(f"Crop saved: {p} ({img.width}x{img.height}px)")

for r in extract(str(p)):
    print(f"  #{r['id']:>3} [{r['type']}] {r['value']}  tol: {r['tolerance']}  ({r['zone']})")
