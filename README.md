# OpenFAIR

Open-source AS9102 First Article Inspection Report (FAIR) generator.

Takes an engineering drawing PDF, extracts every dimension, tolerance, and
GD&T callout using a vision model, and (in progress) produces a ballooned
drawing plus a populated FAIR characteristic accountability form.

Built by an aerospace quality inspector who got tired of ballooning drawings by hand.

## Status

- [x] PDF to 300 DPI image rendering (PyMuPDF)
- [x] Vision extraction of dimensions, tolerances, GD&T frames (~94% on NIST CTC3)
- [x] Tiled full-resolution extraction with deterministic merging
- [x] Automatic drawing ballooning (OpenCV annotation detection)
- [x] AS9102 Form 3 generation (Excel)
- [ ] STEP/DXF import for nominal coordinates and CMM point export
- [ ] Web interface (FastAPI)

## Quick start

Create a venv, install from requirements.txt, set ANTHROPIC_API_KEY, then run
the render module on a drawing PDF followed by the extract module on the PNG.

Test drawings are NIST MBE PMI test cases (public domain).

