#!/usr/bin/env python3
"""Map a Clay table CSV export to Signal Engine ingest JSON (one object per line)."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Clay export header aliases → canonical keys
COLUMN_ALIASES: dict[str, str] = {
    "person work email": "person_work_email",
    "work email": "person_work_email",
    "email": "person_work_email",
    "linkedin url": "person_linkedin_url",
    "person linkedin url": "person_linkedin_url",
    "account domain": "account_domain",
    "company domain": "account_domain",
    "current company domain": "current_company_domain",
    "previous company domain": "previous_company_domain",
    "current title": "current_title",
    "previous title": "previous_title",
    "confidence score": "confidence_score",
    "hs contact id": "hs_contact_id",
    "hubspot contact id": "hs_contact_id",
    "hs company id": "hs_company_id",
    "hubspot company id": "hs_company_id",
    "hs deal id": "hs_deal_id",
    "signal type": "signal_type",
    "detected at": "detected_at",
    "clay row id": "clay_row_id",
    "row id": "clay_row_id",
    "enrichment provider": "enrichment_provider",
    "buyer champion match": "buyer_champion_match",
}


def normalize_header(name: str) -> str:
    key = name.strip().lower().replace("_", " ")
    return COLUMN_ALIASES.get(key, name.strip().lower().replace(" ", "_"))


def parse_bool(value: str | None) -> bool | None:
    if value is None or value == "":
        return None
    lowered = value.strip().lower()
    if lowered in ("true", "1", "yes", "y"):
        return True
    if lowered in ("false", "0", "no", "n"):
        return False
    return None


def parse_confidence(value: str | None) -> float:
    if not value:
        return 0.6
    try:
        score = float(value)
    except ValueError:
        return 0.6
    return max(0.0, min(1.0, score))


def to_iso_utc(value: str | None) -> str:
    if not value or not value.strip():
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    raw = value.strip()
    if raw.endswith("Z") or "+" in raw:
        return raw.replace(" ", "T") if "T" not in raw else raw
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%m/%d/%Y"):
        try:
            dt = datetime.strptime(raw, fmt).replace(tzinfo=timezone.utc)
            return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        except ValueError:
            continue
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def classify_signal(row: dict[str, str]) -> str | None:
    explicit = (row.get("signal_type") or "").strip().lower()
    if explicit in ("job_change", "promotion", "new_hire"):
        return explicit

    old_dom = (row.get("previous_company_domain") or row.get("old_company_domain") or "").strip().lower()
    new_dom = (
        row.get("current_company_domain")
        or row.get("new_company_domain")
        or row.get("account_domain")
        or ""
    ).strip().lower()
    old_title = (row.get("previous_title") or row.get("old_title") or "").strip()
    new_title = (row.get("current_title") or row.get("new_title") or "").strip()

    if row.get("is_new_hire") == "true" or (row.get("table_source") or "") == "new_hire":
        return "new_hire"
    if old_dom and new_dom and old_dom != new_dom:
        return "job_change"
    if old_title and new_title and old_title != new_title:
        return "promotion"
    return None


def company_domain_for_payload(row: dict[str, str], signal_type: str) -> str:
    if signal_type == "job_change":
        return (
            row.get("current_company_domain")
            or row.get("new_company_domain")
            or row.get("account_domain")
            or ""
        ).strip().lower()
    return (row.get("account_domain") or row.get("current_company_domain") or "").strip().lower()


def empty_to_none(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped if stripped else None


def build_idempotency_key(table_id: str, row_id: str, signal_type: str, detected_at: str) -> str:
    day = detected_at[:10] if len(detected_at) >= 10 else "unknown"
    safe_row = re.sub(r"[^a-zA-Z0-9_-]", "", row_id) or "unknown"
    return f"clay:{table_id}:{safe_row}:{signal_type}:{day}"


def row_to_signal(row: dict[str, str], table_id: str, row_index: int) -> dict[str, Any] | None:
    signal_type = classify_signal(row)
    if not signal_type:
        return None

    emit = parse_bool(row.get("emit_signal"))
    if emit is False:
        return None

    detected_at = to_iso_utc(row.get("detected_at"))
    row_id = row.get("clay_row_id") or row.get("row_id") or f"csv_row_{row_index}"
    confidence = parse_confidence(row.get("confidence_score"))
    company_domain = company_domain_for_payload(row, signal_type)
    if not company_domain:
        return None

    payload: dict[str, Any] = {
        "person_full_name": empty_to_none(row.get("person_full_name")),
        "person_email": empty_to_none(row.get("person_work_email")),
        "person_linkedin_url": empty_to_none(row.get("person_linkedin_url")),
        "company_domain": company_domain,
        "company_name": empty_to_none(row.get("account_name") or row.get("current_company_name")),
        "old_title": empty_to_none(row.get("previous_title")),
        "new_title": empty_to_none(row.get("current_title")),
        "old_company_name": empty_to_none(row.get("previous_company_name")),
        "old_company_domain": empty_to_none(row.get("previous_company_domain")),
        "new_company_name": empty_to_none(row.get("current_company_name")),
        "new_company_domain": empty_to_none(row.get("current_company_domain")),
        "buyer_champion_match": parse_bool(row.get("buyer_champion_match")),
        "clay_table_id": table_id,
        "clay_row_id": row_id,
        "clay_enrichment_provider": empty_to_none(row.get("enrichment_provider")),
    }

    signal: dict[str, Any] = {
        "source": "clay",
        "signal_type": signal_type,
        "detected_at": detected_at,
        "confidence": confidence,
        "idempotency_key": build_idempotency_key(table_id, row_id, signal_type, detected_at),
        "hubspot_contact_id": empty_to_none(row.get("hs_contact_id")),
        "hubspot_company_id": empty_to_none(row.get("hs_company_id")),
        "hubspot_deal_id": empty_to_none(row.get("hs_deal_id")),
        "record_state": empty_to_none(row.get("record_state")),
        "status": "new",
        "payload": payload,
    }
    return signal


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="Clay CSV export path")
    parser.add_argument("--output", required=True, type=Path, help="Output JSONL path")
    parser.add_argument(
        "--table-id",
        default="signal_engine_commercial_v1",
        help="Clay table id stored in payload.clay_table_id",
    )
    args = parser.parse_args()

    with args.input.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            print("CSV has no header row", file=sys.stderr)
            return 1
        normalized_fields = [normalize_header(f) for f in reader.fieldnames]
        rows_out = 0
        with args.output.open("w", encoding="utf-8") as out:
            for index, raw_row in enumerate(reader, start=1):
                row = {
                    normalized_fields[i]: (v or "").strip()
                    for i, v in enumerate(raw_row.values())
                }
                signal = row_to_signal(row, args.table_id, index)
                if signal:
                    out.write(json.dumps(signal, separators=(",", ":")) + "\n")
                    rows_out += 1

    print(f"Wrote {rows_out} signal(s) to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
