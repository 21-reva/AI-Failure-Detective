"""Gemini-powered Root Cause Analysis for extracted log errors."""

import json
import logging
import os
import random
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from google import genai
from google.genai import errors, types

from . import log_parser

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

MODEL_NAME = "gemini-3.6-flash"
MAX_ATTEMPTS = 3
BASE_DELAY_SECONDS = 2.0
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
REQUIRED_KEYS = ("severity", "root_cause", "suggested_fix")
MAX_STACK_TRACE_CHARS = 8000
PLACEHOLDER_API_KEY = "your_gemini_api_key_here"

DEFAULT_ANALYSIS_OUTPUT = log_parser.LOGS_DIR / "analysis_results.json"

_client: Optional[genai.Client] = None


class AIConfigurationError(RuntimeError):
    """Raised when the Gemini API is not configured correctly."""


class InvalidAIResponseError(ValueError):
    """Raised when the model response is not valid JSON with the required keys."""


def get_client() -> genai.Client:
    """Return a cached Gemini client, creating it on first use."""
    global _client
    if _client is not None:
        return _client

    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key or api_key == PLACEHOLDER_API_KEY:
        raise AIConfigurationError(
            "GEMINI_API_KEY is not set. Add a valid key to the .env file or "
            "pass it as an environment variable."
        )

    _client = genai.Client(api_key=api_key)
    return _client


def is_api_key_configured() -> bool:
    """Return True if a non-placeholder GEMINI_API_KEY is available."""
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    return bool(api_key) and api_key != PLACEHOLDER_API_KEY


def _truncate_stack_trace(stack_trace: str) -> str:
    """Keep prompts small by trimming very long traces (head and tail preserved)."""
    if len(stack_trace) <= MAX_STACK_TRACE_CHARS:
        return stack_trace
    head = stack_trace[:2000]
    tail = stack_trace[-6000:]
    return f"{head}\n... [stack trace truncated] ...\n{tail}"


def build_prompt(error_record: Dict[str, Any]) -> str:
    """Build the Root Cause Analysis prompt for a single error event."""
    stack_trace = _truncate_stack_trace(str(error_record.get("stack_trace", "")))
    if not stack_trace.strip():
        stack_trace = "(no stack trace was captured for this event)"

    return (
        "You are a senior site reliability engineer performing Root Cause "
        "Analysis (RCA) on an application log error.\n\n"
        "Analyze the following error event and respond with ONLY a JSON object "
        "containing exactly these three keys:\n"
        '  "severity": one of "LOW", "MEDIUM", "HIGH", or "CRITICAL"\n'
        '  "root_cause": a concise explanation of the most likely root cause\n'
        '  "suggested_fix": concrete, actionable steps to fix or mitigate the issue\n\n'
        "Do not include markdown, code fences, or any text outside the JSON object.\n\n"
        "--- ERROR EVENT ---\n"
        f"Timestamp: {error_record.get('timestamp', 'unknown')}\n"
        f"Level: {error_record.get('level', 'unknown')}\n"
        f"Message: {error_record.get('message', '')}\n"
        "Stack trace:\n"
        f"{stack_trace}\n"
        "--- END OF ERROR EVENT ---"
    )


def _to_text(value: Any) -> str:
    """Convert a JSON value to a readable string."""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        return "\n".join(f"- {_to_text(item)}" for item in value)
    return json.dumps(value, ensure_ascii=False)


def parse_and_validate_response(raw_text: Optional[str]) -> Dict[str, str]:
    """Validate that the model output is JSON with severity/root_cause/suggested_fix.

    Raises:
        InvalidAIResponseError: If the output is empty, not JSON, or missing keys.
    """
    if raw_text is None or not raw_text.strip():
        raise InvalidAIResponseError("The model returned an empty response.")

    cleaned = raw_text.strip()
    fenced = re.match(r"^```(?:json)?\s*(.*?)\s*```$", cleaned, re.DOTALL | re.IGNORECASE)
    if fenced:
        cleaned = fenced.group(1).strip()

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise InvalidAIResponseError(f"Model response is not valid JSON: {exc}") from exc

    if isinstance(data, list) and len(data) == 1 and isinstance(data[0], dict):
        data = data[0]

    if not isinstance(data, dict):
        raise InvalidAIResponseError("Model response JSON is not an object.")

    missing = [key for key in REQUIRED_KEYS if key not in data]
    if missing:
        raise InvalidAIResponseError(
            f"Model response is missing required keys: {', '.join(missing)}"
        )

    return {
        "severity": _to_text(data["severity"]).upper(),
        "root_cause": _to_text(data["root_cause"]),
        "suggested_fix": _to_text(data["suggested_fix"]),
    }


def _is_retryable(exc: Exception) -> bool:
    """Decide whether an exception represents a temporary, retryable failure."""
    if isinstance(exc, errors.ServerError):
        return True
    if isinstance(exc, errors.APIError):
        return getattr(exc, "code", None) in RETRYABLE_STATUS_CODES
    if isinstance(exc, (InvalidAIResponseError, ConnectionError, TimeoutError)):
        return True
    return False


def analyze_single_error(error_record: Dict[str, Any]) -> Dict[str, str]:
    """Send one error event to Gemini and return the validated RCA JSON.

    Uses exponential backoff (up to MAX_ATTEMPTS attempts) for temporary
    failures such as HTTP 503, HTTP 429, server errors and malformed output.

    Raises:
        AIConfigurationError: If the API key is not configured.
        Exception: The last error if all attempts fail, or any non-retryable error.
    """
    client = get_client()
    prompt = build_prompt(error_record)
    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        temperature=0.2,
    )

    last_error: Optional[Exception] = None

    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=prompt,
                config=config,
            )
            return parse_and_validate_response(response.text)
        except Exception as exc:  # noqa: BLE001 - classified below
            last_error = exc
            if not _is_retryable(exc) or attempt == MAX_ATTEMPTS:
                break

            delay = BASE_DELAY_SECONDS * (2 ** (attempt - 1)) + random.uniform(0, 0.5)
            logger.warning(
                "Attempt %d/%d failed for error_id=%s (%s: %s). Retrying in %.1fs.",
                attempt,
                MAX_ATTEMPTS,
                error_record.get("error_id"),
                type(exc).__name__,
                exc,
                delay,
            )
            time.sleep(delay)

    assert last_error is not None
    raise last_error


def analyze_error_records(errors_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Run RCA on a list of extracted error records.

    Each returned record is a copy of the input with two extra keys:
    `analysis` (dict with severity/root_cause/suggested_fix, or None) and
    `analysis_error` (string describing the failure, or None).

    Raises:
        AIConfigurationError: If the Gemini API key is missing.
    """
    if errors_list:
        get_client()  # Fail fast on configuration problems.

    results: List[Dict[str, Any]] = []
    for record in errors_list:
        enriched = dict(record)
        try:
            enriched["analysis"] = analyze_single_error(record)
            enriched["analysis_error"] = None
        except AIConfigurationError:
            raise
        except Exception as exc:  # noqa: BLE001 - one failure must not stop the batch
            logger.error(
                "Analysis failed for error_id=%s: %s: %s",
                record.get("error_id"),
                type(exc).__name__,
                exc,
            )
            enriched["analysis"] = None
            enriched["analysis_error"] = f"{type(exc).__name__}: {exc}"
        results.append(enriched)

    return results


def analyze_errors(
    extracted_errors_path: Any = None, output_path: Any = None
) -> List[Dict[str, Any]]:
    """Analyze the errors stored in logs/extracted_errors.json.

    If the JSON file does not exist yet, the log parser is run first. Results
    are saved to logs/analysis_results.json and returned.
    """
    source = Path(extracted_errors_path) if extracted_errors_path else log_parser.DEFAULT_OUTPUT_FILE

    if not source.is_file():
        logger.info("%s not found, running log parser first.", source)
        log_parser.run_log_parser(output_path=source)

    with source.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    error_records = payload.get("errors", []) if isinstance(payload, dict) else payload
    results = analyze_error_records(error_records)

    destination = Path(output_path) if output_path else DEFAULT_ANALYSIS_OUTPUT
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8") as handle:
        json.dump(results, handle, indent=2, ensure_ascii=False)

    logger.info("Saved %d analysis results to %s", len(results), destination)
    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    print(json.dumps(analyze_errors(), indent=2, ensure_ascii=False))
