"""Log parsing utilities for the AI Failure Detective & Log Anomaly Engine.

Parses application log files into structured events using Regex and Pandas.
Multi-line stack traces are grouped under the log event that preceded them.
"""

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOGS_DIR = PROJECT_ROOT / "logs"
DEFAULT_LOG_FILE = LOGS_DIR / "sample_log.log"
DEFAULT_OUTPUT_FILE = LOGS_DIR / "extracted_errors.json"

ERROR_LEVELS = {"ERROR", "CRITICAL"}

# Matches lines such as:
# 2026-10-28 09:14:22,687 [ERROR] app.orders: Unhandled exception ...
LOG_LINE_PATTERN = re.compile(
    r"^(?P<timestamp>\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?)"
    r"\s+\[(?P<level>DEBUG|INFO|WARNING|ERROR|CRITICAL)\]"
    r"\s+(?P<message>.*)$"
)

DATAFRAME_COLUMNS = ["line_number", "timestamp", "level", "message", "stack_trace"]
ERROR_RECORD_COLUMNS = ["line_number", "timestamp", "level", "message", "stack_trace"]


def _normalize_timestamp(raw_timestamp: str) -> str:
    """Convert a raw log timestamp to an ISO-like string with millisecond precision.

    Falls back to the raw string if pandas cannot parse it.
    """
    parsed = pd.to_datetime(raw_timestamp.replace(",", "."), errors="coerce")
    if pd.isna(parsed):
        return raw_timestamp
    return parsed.isoformat(sep=" ", timespec="milliseconds")


def _trim_blank_edges(lines: List[str]) -> List[str]:
    """Remove blank lines from the beginning and end of a list of lines."""
    start = 0
    end = len(lines)
    while start < end and not lines[start].strip():
        start += 1
    while end > start and not lines[end - 1].strip():
        end -= 1
    return lines[start:end]


def _entries_to_dataframe(entries: List[Dict[str, Any]]) -> pd.DataFrame:
    """Build a Pandas DataFrame from the raw parsed entries."""
    if not entries:
        return pd.DataFrame(columns=DATAFRAME_COLUMNS)

    frame = pd.DataFrame(entries)
    frame["timestamp"] = frame["raw_timestamp"].apply(_normalize_timestamp)
    frame["stack_trace"] = frame["trace_lines"].apply(
        lambda lines: "\n".join(_trim_blank_edges(lines))
    )
    return frame[DATAFRAME_COLUMNS].reset_index(drop=True)


def parse_log_text(log_text: str) -> pd.DataFrame:
    """Parse raw log text into a DataFrame of log events.

    Every line that matches the log header pattern starts a new event. Any
    non-matching lines (e.g. stack trace lines) are attached to the most
    recent event as its stack trace context.

    Args:
        log_text: The full text of a log file.

    Returns:
        DataFrame with columns: line_number, timestamp, level, message, stack_trace.
    """
    entries: List[Dict[str, Any]] = []
    current: Optional[Dict[str, Any]] = None

    for line_number, line in enumerate(log_text.splitlines(), start=1):
        match = LOG_LINE_PATTERN.match(line)
        if match:
            if current is not None:
                entries.append(current)
            current = {
                "line_number": line_number,
                "raw_timestamp": match.group("timestamp"),
                "level": match.group("level").upper(),
                "message": match.group("message").strip(),
                "trace_lines": [],
            }
        elif current is not None:
            current["trace_lines"].append(line.rstrip())

    if current is not None:
        entries.append(current)

    return _entries_to_dataframe(entries)


def parse_log_file(log_file_path: Any) -> pd.DataFrame:
    """Parse a log file from disk into a DataFrame of log events.

    Args:
        log_file_path: Path to a `.log` or `.txt` file.

    Returns:
        DataFrame with columns: line_number, timestamp, level, message, stack_trace.

    Raises:
        FileNotFoundError: If the file does not exist.
    """
    path = Path(log_file_path)
    if not path.is_file():
        raise FileNotFoundError(f"Log file not found: {path}")

    log_text = path.read_text(encoding="utf-8", errors="replace")
    return parse_log_text(log_text)


def extract_error_records(log_dataframe: pd.DataFrame) -> List[Dict[str, Any]]:
    """Extract ERROR and CRITICAL events (with stack traces) as JSON-ready dicts."""
    if log_dataframe.empty:
        return []

    error_frame = log_dataframe[log_dataframe["level"].isin(ERROR_LEVELS)]
    records: List[Dict[str, Any]] = []

    for position, row in enumerate(
        error_frame[ERROR_RECORD_COLUMNS].to_dict(orient="records"), start=1
    ):
        records.append(
            {
                "error_id": position,
                "line_number": int(row["line_number"]),
                "timestamp": str(row["timestamp"]),
                "level": str(row["level"]),
                "message": str(row["message"]),
                "stack_trace": str(row["stack_trace"]),
            }
        )

    return records


def save_errors_json(
    error_records: List[Dict[str, Any]],
    source_name: str,
    total_log_entries: int,
    output_path: Any = None,
) -> Path:
    """Save extracted error records as structured JSON.

    Args:
        error_records: Records produced by `extract_error_records`.
        source_name: Name of the file or input the records came from.
        total_log_entries: Total number of log events parsed.
        output_path: Destination JSON path (defaults to logs/extracted_errors.json).

    Returns:
        The path the JSON file was written to.
    """
    destination = Path(output_path) if output_path else DEFAULT_OUTPUT_FILE
    destination.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "source": source_name,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "total_log_entries": total_log_entries,
        "total_errors": len(error_records),
        "errors": error_records,
    }

    with destination.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)

    return destination


def run_log_parser(
    log_file_path: Any = None, output_path: Any = None
) -> List[Dict[str, Any]]:
    """Parse a log file, extract ERROR/CRITICAL events and save them as JSON.

    Args:
        log_file_path: Log file to parse (defaults to logs/sample_log.log).
        output_path: Where to write the JSON output
            (defaults to logs/extracted_errors.json).

    Returns:
        List of extracted error records.
    """
    source_path = Path(log_file_path) if log_file_path else DEFAULT_LOG_FILE
    log_dataframe = parse_log_file(source_path)
    error_records = extract_error_records(log_dataframe)

    destination = save_errors_json(
        error_records=error_records,
        source_name=source_path.name,
        total_log_entries=len(log_dataframe),
        output_path=output_path,
    )
    logger.info(
        "Parsed %d log entries, extracted %d errors -> %s",
        len(log_dataframe),
        len(error_records),
        destination,
    )
    return error_records


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    extracted = run_log_parser()
    print(f"Extracted {len(extracted)} error events to {DEFAULT_OUTPUT_FILE}")