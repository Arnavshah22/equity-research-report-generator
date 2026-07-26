"""
FastAPI app: upload a context document, get a research-note PDF back.

Generation is synchronous but runs in a worker thread -- extraction can take
a minute or two on a long filing, and Playwright's sync API cannot run inside
the event loop thread.
"""

from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool

from .extract import SUPPORTED, UnsupportedDocument, extract_text
from .llm import ExtractionError, backend_label, extract_report, has_api_key
from .render import render_pdf

BASE_DIR = Path(__file__).parent
OUTPUT_DIR = BASE_DIR.parent / "output"
MAX_UPLOAD_BYTES = 25 * 1024 * 1024

app = FastAPI(title="Equity Research Report Generator")


def _safe_slug(name: str) -> str:
    keep = [c if c.isalnum() else "_" for c in name.strip()]
    slug = "".join(keep).strip("_") or "report"
    return slug[:60]


@app.get("/api/health")
def health() -> dict:
    """Lets the UI tell the user up front whether extraction will be live."""
    return {
        "status": "ok",
        "llm_configured": has_api_key(),
        "llm_backend": backend_label(),
        "supported_formats": SUPPORTED,
    }


@app.post("/api/generate")
async def generate(
    company_name: str = Form(...),
    file: UploadFile = File(...),
) -> JSONResponse:
    data = await file.read()
    if not data:
        raise HTTPException(400, "The uploaded file is empty.")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "File exceeds the 25 MB limit.")

    try:
        text = extract_text(file.filename or "upload", data)
    except UnsupportedDocument as exc:
        raise HTTPException(400, str(exc)) from exc

    try:
        report, used_llm = await run_in_threadpool(
            extract_report, company_name, text, file.filename or "upload"
        )
    except ExtractionError as exc:
        raise HTTPException(502, str(exc)) from exc

    report_id = f"{_safe_slug(company_name)}_{uuid.uuid4().hex[:8]}"
    out_path = OUTPUT_DIR / f"{report_id}.pdf"

    try:
        await run_in_threadpool(render_pdf, report, out_path)
    except Exception as exc:  # rendering failures are environmental, not user error
        raise HTTPException(500, f"PDF generation failed: {exc}") from exc

    return JSONResponse(
        {
            "report_id": report_id,
            "download_url": f"/api/download/{report_id}",
            "used_llm": used_llm,
            "company_name": report.header.company_name,
            "rating": report.header.rating.value if report.header.rating else None,
            "chars_extracted": len(text),
        }
    )


@app.get("/api/download/{report_id}")
def download(report_id: str) -> FileResponse:
    # Reject anything that isn't a plain generated id so the path can't escape
    # the output directory.
    if not report_id.replace("_", "").isalnum():
        raise HTTPException(400, "Invalid report id.")

    path = OUTPUT_DIR / f"{report_id}.pdf"
    if not path.is_file():
        raise HTTPException(404, "Report not found.")

    return FileResponse(
        path,
        media_type="application/pdf",
        filename=f"{report_id}.pdf",
    )


# Mounted last so the API routes above take precedence.
app.mount("/", StaticFiles(directory=BASE_DIR / "static", html=True), name="static")
