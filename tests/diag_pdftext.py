"""Diagnostic: what text does the PDF actually contain?"""
import fitz

doc = fitz.open("samples/public/nist_ctc3.pdf")
page = doc[0]
text = page.get_text().strip()
print(f"--- {len(text)} chars of text on page 1 ---")
print(text[:2000] if text else "(none)")
