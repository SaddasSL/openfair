"""Render PDF drawing pages to PNG images for vision extraction."""
import sys
from pathlib import Path

import fitz  # PyMuPDF


def render_pdf(pdf_path: str, out_dir: str = "output", dpi: int = 300) -> list[Path]:
    """Render each page of a PDF to a PNG. Returns list of image paths."""
    pdf_file = Path(pdf_path)
    out = Path(out_dir)
    out.mkdir(exist_ok=True)

    doc = fitz.open(pdf_file)
    image_paths = []
    for i, page in enumerate(doc, start=1):
        pix = page.get_pixmap(dpi=dpi)
        img_path = out / f"{pdf_file.stem}_page{i}.png"
        pix.save(img_path)
        image_paths.append(img_path)
        print(f"Rendered page {i}: {img_path}  ({pix.width}x{pix.height}px)")
    doc.close()
    return image_paths


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: py -m src.extraction.render <pdf_path>")
        sys.exit(1)
    render_pdf(sys.argv[1])
