"""FastAPI application for the AI Failure Detective & Log Anomaly Engine."""

import logging
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from . import ai_analyzer, log_parser

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 MB
ALLOWED_EXTENSIONS = (".log", ".txt")

app = FastAPI(
    title="AI Failure Detective & Log Anomaly Engine",
    description=(
        "Parses application logs, isolates multi-line error stack traces and "
        "uses Google Gemini to produce Root Cause Analysis."
    ),
    version="1.0.0",
)


class RawLogInput(BaseModel):
    """Payload for the /analyze-text endpoint."""

    log_text: str = Field(
        ...,
        min_length=1,
        description="Raw log content, including multi-line stack traces.",
    )


class Analysis(BaseModel):
    """Structured Root Cause Analysis returned by Gemini."""

    severity: str
    root_cause: str
    suggested_fix: str


class Finding(BaseModel):
    """A single error event combined with its AI analysis."""

    error_id: int
    line_number: int
    timestamp: str
    level: str
    message: str
    stack_trace: str
    analysis: Optional[Analysis] = None
    analysis_error: Optional[str] = None


class AnalysisResponse(BaseModel):
    """Combined parsing and analysis results."""

    source: str
    total_log_entries: int
    total_errors_found: int
    analyzed_successfully: int
    findings: List[Finding]


def _build_response(source: str, log_text: str) -> AnalysisResponse:
    """Parse log text, run AI analysis on extracted errors and combine results."""
    log_dataframe = log_parser.parse_log_text(log_text)
    error_records = log_parser.extract_error_records(log_dataframe)

    if not error_records:
        return AnalysisResponse(
            source=source,
            total_log_entries=len(log_dataframe),
            total_errors_found=0,
            analyzed_successfully=0,
            findings=[],
        )

    try:
        analyzed: List[Dict[str, Any]] = ai_analyzer.analyze_error_records(error_records)
    except ai_analyzer.AIConfigurationError as exc:
        logger.error("AI configuration error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    successes = sum(1 for item in analyzed if item.get("analysis") is not None)

    return AnalysisResponse(
        source=source,
        total_log_entries=len(log_dataframe),
        total_errors_found=len(error_records),
        analyzed_successfully=successes,
        findings=[Finding(**item) for item in analyzed],
    )


@app.get("/health")
def health() -> Dict[str, Any]:
    """Liveness probe with basic configuration status."""
    return {
        "status": "ok",
        "model": ai_analyzer.MODEL_NAME,
        "gemini_api_key_configured": ai_analyzer.is_api_key_configured(),
    }


@app.post("/analyze-text", response_model=AnalysisResponse)
def analyze_text(payload: RawLogInput) -> AnalysisResponse:
    """Analyze raw log text submitted as a JSON payload."""
    if not payload.log_text.strip():
        raise HTTPException(status_code=400, detail="log_text must not be blank.")
    return _build_response(source="raw_text_input", log_text=payload.log_text)


@app.post("/analyze-file", response_model=AnalysisResponse)
def analyze_file(file: UploadFile = File(...)) -> AnalysisResponse:
    """Analyze an uploaded `.log` or `.txt` file."""
    filename = file.filename or ""
    if not filename.lower().endswith(ALLOWED_EXTENSIONS):
        raise HTTPException(
            status_code=400,
            detail="Unsupported file type. Please upload a .log or .txt file.",
        )

    content = file.file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size is {MAX_UPLOAD_BYTES // (1024 * 1024)} MB.",
        )
    if not content.strip():
        raise HTTPException(status_code=400, detail="The uploaded file is empty.")

    log_text = content.decode("utf-8", errors="replace")
    return _build_response(source=filename, log_text=log_text)