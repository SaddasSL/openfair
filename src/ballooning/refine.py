"""Refine vision-estimated bboxes using the PDF's authoritative text layer."""
import json
import re
import sys
from pathlib import Path

import fitz  # PyMuPDF


def search_token(value: str) -> str | None:
    """Pick the most distinctive searchable text from a callout value."""
    if not value:
        return None
    # longest number-like token, e.g. .438, 2.00, 1.065, .005
    nums = re.findall(r"\d*\.\d+|\d+\.\d*|\d+", value)
    if nums:
        return max(nums, key=len)
    # fall back to first words for text notes
    words = value.split()
    return " ".join(words[:3]) if words else None


def refine(pdf_path: str, json_path: str, dpi: int = 300, page_no: int = 0) -> None:
    scale = dpi / 72  # PDF points -> rendered pixels
    doc = fitz.open(pdf_path)
    page = doc[page_no]
    entries = json.loads(Path(json_path).read_text(encoding="utf-8"))

    refined = missed = 0
    for e in entries:
        token = search_token(e.get("value") or "")
        if not token:
            continue
        hits = page.search_for(token)
        if not hits:
            missed += 1
            print(f"  no PDF match for #{e['id']} token '{token}' - keeping estimate")
            continue
        est = e.get("bbox") or [0, 0, 0, 0]
        ecx, ecy = est[0] + est[2] / 2, est[1] + est[3] / 2
        best = min(hits, key=lambda r: ((r.x0 + r.x1) / 2 * scale - ecx) ** 2
                                       + ((r.y0 + r.y1) / 2 * scale - ecy) ** 2)
        e["bbox"] = [round(best.x0 * scale), round(best.y0 * scale),
                     round((best.x1 - best.x0) * scale), round((best.y1 - best.y0) * scale)]
        e["bbox_source"] = "pdf"
        refined += 1

    doc.close()
    Path(json_path).write_text(json.dumps(entries, indent=2, ensure_ascii=False),
                               encoding="utf-8")
    print(f"Refined {refined} positions from PDF text layer, {missed} kept as estimates")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: py -m src.ballooning.refine <pdf_path> <extracted_json>")
        sys.exit(1)
    refine(sys.argv[1], sys.argv[2])
