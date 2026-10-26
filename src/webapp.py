"""OpenFAIR web interface: upload a drawing PDF, download the FAIR package.

    uvicorn src.webapp:app --port 8000

Set OPENFAIR_TOKEN to require an access token (sent as the "token" form field
or ?token= query parameter). Each run gets its own folder, and files can only
be fetched by their job id.
"""
from __future__ import annotations

import html
import os
import re
import secrets
import uuid
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, HTMLResponse

from src.pipeline import run_pipeline

JOBS = Path(os.environ.get("OPENFAIR_JOBS", "output/jobs"))
TOKEN = os.environ.get("OPENFAIR_TOKEN", "")
MAX_BYTES = 25 * 1024 * 1024
app = FastAPI(title="OpenFAIR")

PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8"><title>OpenFAIR</title>
<meta name="viewport" content="width=device-width,initial-scale=1"><style>
body{{font-family:system-ui,sans-serif;max-width:900px;margin:40px auto;padding:0 16px;color:#1d2731}}
h1{{color:#1a4d8f;margin-bottom:4px}} .card{{border:1px solid #d6dde3;border-radius:8px;padding:20px;margin:16px 0}}
img{{max-width:100%;border:1px solid #ccd}} a.btn{{display:inline-block;background:#1a4d8f;color:#fff;
padding:10px 16px;border-radius:6px;text-decoration:none;margin:0 8px 8px 0}}
input,button{{font-size:15px;padding:8px}} button{{background:#1a4d8f;color:#fff;border:0;border-radius:6px;
padding:10px 20px;cursor:pointer}} .warn{{background:#fff4d6;padding:10px;border-radius:6px}}</style></head><body>
<h1>OpenFAIR</h1><p>Upload an engineering drawing PDF and get a ballooned drawing plus AS9102 Forms 1, 2 and 3.</p>
<p class="warn">The drawing is sent to the configured vision API for reading. Do not upload export controlled
or customer proprietary drawings unless your organisation has approved this.</p>{body}</body></html>"""

FORM = """<div class="card"><form action="/run" method="post" enctype="multipart/form-data">
<p><input type="file" name="pdf" accept=".pdf,application/pdf" required></p>
<p><input name="part_number" placeholder="Part number"> <input name="part_name" placeholder="Part name">
<input name="order_number" placeholder="Order number"></p>{token_field}
<p><button>Generate FAIR package</button></p>
<p><small>About 1 to 2 minutes per page.</small></p></form></div>"""


def _check(token: str):
    if TOKEN and not secrets.compare_digest(token or "", TOKEN):
        raise HTTPException(status_code=401, detail="access token required")


def _form(token: str = "") -> str:
    field = (f'<p><input type="password" name="token" placeholder="Access token" value="{html.escape(token)}"></p>'
             if TOKEN else "")
    return FORM.format(token_field=field)


@app.get("/", response_class=HTMLResponse)
def home():
    return PAGE.format(body=_form())


@app.post("/run", response_class=HTMLResponse)
def run(pdf: UploadFile = File(...), part_number: str = Form(""), part_name: str = Form(""),
        order_number: str = Form(""), token: str = Form("")):
    _check(token)
    data = pdf.file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise HTTPException(status_code=413, detail="file larger than 25 MB")
    if not data.startswith(b"%PDF"):
        raise HTTPException(status_code=400, detail="please upload a PDF drawing")
    job = uuid.uuid4().hex
    folder = JOBS / job
    folder.mkdir(parents=True)
    pdf_path = folder / "drawing.pdf"
    pdf_path.write_bytes(data)
    try:
        res = run_pipeline(str(pdf_path), part_number, part_name, order_number, out_dir=str(folder))
    except Exception as exc:
        return PAGE.format(body=f'<div class="card"><b>Pipeline failed:</b> {html.escape(str(exc))}</div>'
                           + _form(token))
    q = f"?token={html.escape(token)}" if TOKEN else ""
    links = "".join(f'<a class="btn" href="/files/{job}/{Path(res[k]).name}{q}" download>{label}</a>'
                    for k, label in (("ballooned_pdf", "Ballooned drawing (PDF)"),
                                     ("workbook", "AS9102 Forms 1-3 (Excel)"),
                                     ("json", "Characteristics (JSON)")))
    preview = f'<img src="/files/{job}/{Path(res["ballooned_pages"][0]).name}{q}" alt="Ballooned page 1">'
    warn = "".join(f'<p class="warn">{html.escape(w)}</p>' for w in res["warnings"])
    body = (f'<div class="card"><h3>{html.escape(pdf.filename or "drawing")}: {res["characteristics"]} '
            f'characteristics on {res["pages"]} page(s)</h3>{warn}<p>{links}</p>{preview}</div>')
    return PAGE.format(body=body + _form(token))


@app.get("/files/{job}/{name}")
def files(job: str, name: str, token: str = Query("")):
    _check(token)
    if not re.fullmatch(r"[0-9a-f]{32}", job) or not re.fullmatch(r"[\w.-]+", name):
        raise HTTPException(status_code=404)
    path = (JOBS / job / name).resolve()
    if JOBS.resolve() not in path.parents or not path.is_file():
        raise HTTPException(status_code=404)
    return FileResponse(path)
