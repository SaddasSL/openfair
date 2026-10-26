"""Render every page of a PDF drawing to PNG for vision extraction."""
from __future__ import annotations

import sys
from pathlib import Path

import fitz  # PyMuPDF

DPI = 300


def render_pdf(pdf_path: str, out_dir: str = "output", dpi: int = DPI) -> list[Path]:
    """Render each page to <stem>_page<N>.png. Returns the image paths in page order."""
    pdf_file = Path(pdf_path)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    paths = []
    with fitz.open(pdf_file) as doc:
        if doc.page_count == 0:
            raise ValueError(f"{pdf_file.name} has no pages")
        for i, page in enumerate(doc, start=1):
            pix = page.get_pixmap(dpi=dpi)
            img_path = out / f"{pdf_file.stem}_page{i}.png"
            pix.save(img_path)
            paths.append(img_path)
            print(f"Rendered page {i}: {img_path} ({pix.width}x{pix.height}px)")
    return paths


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m src.extraction.render <pdf_path>")
        sys.exit(1)
    render_pdf(sys.argv[1])
