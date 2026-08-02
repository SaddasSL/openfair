"""Single entry point: run the full OpenFAIR pipeline on a drawing PDF."""
import sys
from pathlib import Path

from src.ballooning.balloon import balloon
from src.ballooning.snap import snap
from src.extraction.render import render_pdf
from src.extraction.tiled import merge_tiles
from src.reports.form3 import form3
import json


def run_pipeline(pdf_path: str, part_number: str = "", part_name: str = "",
                 order_number: str = "", out_dir: str = "output") -> dict:
    """PDF in -> ballooned drawing + Form 3 out. Returns paths of all artifacts."""
    print(f"[1/5] Rendering {pdf_path}...")
    images = render_pdf(pdf_path, out_dir)
    image_path = str(images[0])  # v1: first page only

    print("[2/5] Extracting characteristics (vision, ~6 API calls)...")
    entries = merge_tiles(image_path)
    json_path = Path(out_dir) / (Path(image_path).stem + "_tiled.json")
    json_path.write_text(json.dumps(entries, indent=2, ensure_ascii=False),
                         encoding="utf-8")
    print(f"      {len(entries)} characteristics")

    print("[3/5] Snapping to annotation clusters...")
    snap(image_path, str(json_path))

    print("[4/5] Drawing balloons...")
    ballooned = balloon(image_path, str(json_path))

    print("[5/5] Generating Form 3...")
    xlsx = form3(str(json_path), part_number, part_name, order_number)

    return {"image": image_path, "json": str(json_path),
            "ballooned": str(ballooned), "form3": str(xlsx)}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: py -m src.pipeline <pdf_path> [part_number] [part_name]")
        sys.exit(1)
    results = run_pipeline(sys.argv[1],
                           sys.argv[2] if len(sys.argv) > 2 else "",
                           sys.argv[3] if len(sys.argv) > 3 else "")
    print("\nDone:")
    for k, v in results.items():
        print(f"  {k}: {v}")

