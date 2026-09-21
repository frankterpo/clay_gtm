#!/usr/bin/env python3
"""Validate Clay signal ingest JSON file(s) against the PoC schema."""

from __future__ import annotations

import json
import sys
from pathlib import Path

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "schemas" / "clay-signal-ingest.schema.json"

REQUIRED_TOP = ("source", "signal_type", "detected_at", "confidence", "payload")
VALID_SIGNAL_TYPES = ("job_change", "promotion", "new_hire")
VALID_RECORD_STATES = ("ghosted", "stuck", "active", "closed_lost", None)


def load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def validate_payload(data: dict, path: str) -> list[str]:
    errors: list[str] = []

    for key in REQUIRED_TOP:
        if key not in data:
            errors.append(f"{path}: missing required field '{key}'")

    if data.get("source") != "clay":
        errors.append(f"{path}: source must be 'clay'")

    signal_type = data.get("signal_type")
    if signal_type not in VALID_SIGNAL_TYPES:
        errors.append(f"{path}: invalid signal_type '{signal_type}'")

    confidence = data.get("confidence")
    if not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
        errors.append(f"{path}: confidence must be a number between 0 and 1")

    record_state = data.get("record_state")
    if record_state not in VALID_RECORD_STATES:
        errors.append(f"{path}: invalid record_state '{record_state}'")

    payload = data.get("payload")
    if not isinstance(payload, dict):
        errors.append(f"{path}: payload must be an object")
        return errors

    if not payload.get("company_domain"):
        errors.append(f"{path}: payload.company_domain is required")

    if signal_type == "job_change":
        for field in ("old_company_domain", "new_company_domain", "new_title"):
            if not payload.get(field):
                errors.append(f"{path}: job_change requires payload.{field}")
    elif signal_type == "promotion":
        for field in ("old_title", "new_title"):
            if not payload.get(field):
                errors.append(f"{path}: promotion requires payload.{field}")
    elif signal_type == "new_hire":
        if not payload.get("new_title"):
            errors.append(f"{path}: new_hire requires payload.new_title")
        if not payload.get("person_linkedin_url"):
            errors.append(f"{path}: new_hire requires payload.person_linkedin_url")

    return errors


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(f"Usage: {argv[0]} <payload.json> [...]", file=sys.stderr)
        return 1

    if not SCHEMA_PATH.is_file():
        print(f"Schema not found: {SCHEMA_PATH}", file=sys.stderr)
        return 1

    all_errors: list[str] = []
    for arg in argv[1:]:
        path = Path(arg)
        try:
            data = load_json(path)
        except (OSError, json.JSONDecodeError) as exc:
            all_errors.append(f"{path}: {exc}")
            continue
        all_errors.extend(validate_payload(data, str(path)))

    if all_errors:
        for err in all_errors:
            print(err, file=sys.stderr)
        return 1

    print(f"OK: {len(argv) - 1} file(s) validated against {SCHEMA_PATH.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
