"""Run the full OpenFAIR pipeline on a drawing PDF.

    python -m src.pipeline drawing.pdf --part-number 123-456 --part-name Bracket

Outputs (in --out, default ./output):
    <stem>_characteristics.json   every extracted characteristic with page, zone and balloon
    <stem>_ballooned.pdf          all pages with numbered balloons (plus one PNG per page)
    <stem>_FAIR.xlsx              AS9102 Forms 1, 2 and 3 plus an inspection plan sheet

Use --from-json to rebuild balloons and forms from a saved characteristics file
without calling the vision model again (after hand corrections, for example).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import fitz  # PyMuPDF

from src.ballooning.balloon import draw_page, number_entries, save_pdf
from src.ballooning.locate import locate
from src.extraction.render import DPI, render_pdf
from src.reports.fair import build_workbook
from src.zones import grid_for_page, reference_location


def run_pipeline(pdf_path: str, part_number: str = "", part_name: str = "",
                 order_number: str = "", out_dir: str = "output", zones: str | None = None,
                 zone_standard: str = "asme", from_json: str | None = None,
                 extractor=None, title_extractor=None) -> dict:
    """PDF in -> characteristics JSON, ballooned PDF and FAIR workbook out."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    stem = Path(pdf_path).stem
    print(f"[1/5] Rendering {pdf_path}")
    images = render_pdf(pdf_path, str(out))
    doc = fitz.open(pdf_path)
    warnings: list[str] = []

    if from_json:
        saved = json.loads(Path(from_json).read_text(encoding="utf-8"))
        entries, title = saved["characteristics"], saved.get("title_block", {})
        print(f"[2/5] Loaded {len(entries)} characteristics from {from_json}")
    else:
        from src.extraction.tiled import merge_tiles
        entries, title = [], {}
        for page_no, image in enumerate(images, start=1):
            print(f"[2/5] Extracting page {page_no}/{len(images)} (6 tiles)")
            page_entries = merge_tiles(str(image), extractor)
            for e in page_entries:
                e["page"] = page_no
            entries += page_entries
        try:
            if title_extractor is None:
                from src.extraction.extract import extract_title_block as title_extractor
            title = title_extractor(str(images[0])) or {}
        except Exception as exc:  # title block is helpful, never essential
            warnings.append(f"title block not read: {exc}")
            title = {}

    print("[3/5] Locating callouts and drawing zones")
    grids = {}
    for page_no, image in enumerate(images, start=1):
        page_entries = [e for e in entries if e.get("page", 1) == page_no]
        counts = locate(page_entries, str(image), doc[page_no - 1], DPI)
        grids[page_no] = grid_for_page(doc[page_no - 1], zones, zone_standard)
        how = ", ".join(f"{k} {v}" for k, v in counts.items() if v)
        print(f"      page {page_no}: {how or 'no callouts'}; zones "
              f"{'from drawing border' if grids[page_no].detected else 'estimated grid'}")
        for e in page_entries:
            if e.get("bbox"):
                e["reference_location"] = reference_location(page_no, grids[page_no], e["bbox"], DPI)
    doc.close()

    print("[4/5] Ballooning")
    entries.sort(key=lambda e: (e.get("page", 1), e.get("id", 0)))
    for i, e in enumerate(entries, start=1):
        e["id"] = i
    total = number_entries(entries)
    pages = [draw_page(str(img), [e for e in entries if e.get("page", 1) == n],
                       out / f"{stem}_page{n}_ballooned.png")
             for n, img in enumerate(images, start=1)]
    ballooned_pdf = save_pdf(pages, out / f"{stem}_ballooned.pdf", DPI)

    print("[5/5] Writing AS9102 workbook")
    info = {"part_number": part_number or title.get("part_number") or "",
            "part_name": part_name or title.get("part_name") or "",
            "drawing_number": title.get("drawing_number") or "",
            "revision": title.get("revision") or "",
            "material": title.get("material") or "",
            "specifications": title.get("specifications") or [],
            "order_number": order_number}
    xlsx = build_workbook(entries, info, out / f"{stem}_FAIR.xlsx")
    json_path = out / f"{stem}_characteristics.json"
    json_path.write_text(json.dumps({"drawing": Path(pdf_path).name, "title_block": title,
                                     "characteristics": entries}, indent=2, ensure_ascii=False),
                         encoding="utf-8")
    print(f"Done: {len(entries)} callouts, {total} ballooned characteristics on {len(images)} page(s)")
    for w in warnings:
        print(f"Warning: {w}")
    return {"json": str(json_path), "ballooned_pdf": str(ballooned_pdf),
            "ballooned_pages": [str(p) for p in pages], "workbook": str(xlsx),
            "characteristics": total, "pages": len(images), "warnings": warnings}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Generate an AS9102 FAIR package from a drawing PDF.")
    ap.add_argument("pdf")
    ap.add_argument("--part-number", default="")
    ap.add_argument("--part-name", default="")
    ap.add_argument("--order-number", default="")
    ap.add_argument("--out", default="output")
    ap.add_argument("--zones", help="override the zone grid as COLSxROWS, e.g. 8x4")
    ap.add_argument("--zone-standard", choices=["asme", "iso"], default="asme",
                    help="numbering for estimated grids (default asme)")
    ap.add_argument("--from-json", help="reuse a saved *_characteristics.json instead of extracting")
    a = ap.parse_args(argv)
    res = run_pipeline(a.pdf, a.part_number, a.part_name, a.order_number, a.out,
                       a.zones, a.zone_standard, a.from_json)
    for k in ("json", "ballooned_pdf", "workbook"):
        print(f"  {k}: {res[k]}")


if __name__ == "__main__":
    main()
