"""OpenFAIR web interface - thin skin over the pipeline."""
import shutil
import uuid
from pathlib import Path

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from src.pipeline import run_pipeline

app = FastAPI(title="OpenFAIR")
Path("output").mkdir(exist_ok=True)
app.mount("/output", StaticFiles(directory="output"), name="output")

PAGE = """<!doctype html><html><head><title>OpenFAIR</title><style>
body{{font-family:system-ui,sans-serif;max-width:860px;margin:40px auto;padding:0 16px;color:#222}}
h1{{color:#1a4d8f}} .card{{border:1px solid #ddd;border-radius:8px;padding:20px;margin:16px 0}}
img{{max-width:100%;border:1px solid #ccc}} a.btn{{display:inline-block;background:#1a4d8f;
color:#fff;padding:10px 18px;border-radius:6px;text-decoration:none;margin-right:10px}}
input,button{{font-size:15px;padding:8px}} button{{background:#1a4d8f;color:#fff;border:0;
border-radius:6px;padding:10px 20px;cursor:pointer}}</style></head><body>
<h1>OpenFAIR</h1><p>AS9102 FAIR generator &mdash; upload a drawing PDF, get a ballooned
drawing and Form 3.</p>{body}</body></html>"""

FORM = """<div class=card><form action=/run method=post enctype=multipart/form-data>
<p><input type=file name=pdf accept=.pdf required></p>
<p><input name=part_number placeholder="Part number"> <input name=part_name placeholder="Part name"> <input name=order_number placeholder="Order number"></p>
<p><button>Generate FAIR package</button></p>
<p><small>Processing takes 1&ndash;2 minutes (vision extraction runs ~6 API calls).</small></p>
</form></div>"""


@app.get("/", response_class=HTMLResponse)
def home():
    return PAGE.format(body=FORM)


@app.post("/run", response_class=HTMLResponse)
def run(pdf: UploadFile = File(...), part_number: str = Form(""), part_name: str = Form(""), order_number: str = Form("")):
    job = uuid.uuid4().hex[:8]
    pdf_path = Path("output") / f"upload_{job}.pdf"
    with pdf_path.open("wb") as f:
        shutil.copyfileobj(pdf.file, f)
    try:
        results = run_pipeline(str(pdf_path), part_number, part_name, order_number=order_number)
    except Exception as exc:
        return PAGE.format(body=f"<div class=card><b>Pipeline failed:</b> {exc}</div>" + FORM)
    ballooned = Path(results["ballooned"]).name
    xlsx = Path(results["form3"]).name
    body = f"""<div class=card><h3>Done - {pdf.filename}</h3>
<p><a class=btn href="/output/{ballooned}" download>Download ballooned drawing</a>
<a class=btn href="/output/{xlsx}" download>Download Form 3 (Excel)</a></p>
<img src="/output/{ballooned}"></div>""" + FORM
    return PAGE.format(body=body)


