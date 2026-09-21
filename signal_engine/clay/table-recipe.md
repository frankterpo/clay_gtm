# Clay table recipe — Signal Engine commercial v1

Dedicated workbook for **job_change**, **promotion**, and **new_hire**. This is **not** the RB2B table (`t_0t6nmvhh4tbjH6sKTWd`).

Suggested workbook name: **Signal Engine — Commercial (PoC v1)**  
Suggested table name: **`signal_engine_commercial_v1`**  
Record `clay_table_id` in payloads after creation (Clay UI → table settings / API).

## Why table webhooks (not workflow triggers)

Workflow **webhook triggers** can be plan-blocked. Prefer:

1. **Table webhook** — fires on row create/update when a formula `emit_signal` = true.
2. **HTTP API column** — POST `{{signal_ingest_json}}` to ingest URL (rate-limit aware).
3. **Scheduled export** — CSV → `map_clay_row_to_signal.py` → batch POST (fallback).

## Table A — ICP contacts (job change / promotion monitor)

**Input rows**: HubSpot export or Clay source of ICP contacts (pilot segment: PE / private credit, deal created last 12 months).

| Column | Type | Purpose |
|--------|------|---------|
| `person_full_name` | Text | |
| `person_work_email` | Email | HS match key |
| `person_linkedin_url` | URL | Enrichment input |
| `account_domain` | Text | Company apex domain |
| `account_name` | Text | |
| `hs_contact_id` | Text | HubSpot lookup (read) |
| `hs_company_id` | Text | HubSpot lookup (read) |
| `hs_deal_id` | Text | Optional |
| `record_state` | Text | ghosted / stuck / active / closed_lost (from HS sync) |
| `previous_title` | Text | Snapshot before enrichment |
| `current_title` | Text | From **Enrich Person** / job change provider |
| `previous_company_name` | Text | |
| `previous_company_domain` | Text | |
| `current_company_name` | Text | |
| `current_company_domain` | Text | |
| `enrichment_provider` | Text | Provider name |
| `detected_at` | Date | Change detected timestamp |
| `confidence_score` | Number | 0–1 |
| `signal_type` | Formula | `job_change` / `promotion` / blank |
| `emit_signal` | Formula | true when classified + confidence ≥ threshold |
| `idempotency_key` | Formula | See mapping doc |
| `signal_ingest_json` | Formula (JSON) | Full ingest body |
| `ingest_status` | Text | last HTTP status (optional) |

### Enrichment stack (order)

1. **Enrich Person** — `person_linkedin_url` or `person_work_email` → refresh title + company.
2. Job change column pack (workspace-specific): e.g. Mixrank / PDL “job change” or compare `previous_*` vs `current_*` on schedule.
3. **HubSpot** — *Find* contact by email, company by domain → fill `hs_*` only.

### Classification formulas (conceptual)

```
// signal_type (simplified)
IF(previous_company_domain != "" AND current_company_domain != "" AND previous_company_domain != current_company_domain, "job_change",
  IF(previous_title != "" AND current_title != "" AND previous_title != current_title AND previous_company_domain == current_company_domain, "promotion", ""))
```

```
// emit_signal
signal_type != "" AND confidence_score >= 0.6
```

### Webhook wiring

1. Add column `signal_ingest_json` building the unified object (`source` = `clay`).
2. Table settings → **Webhooks** → URL = Edge Function ingest URL.
3. Filter: only rows where `emit_signal` is true (Clay filter or webhook condition if supported).
4. Body: raw JSON from `signal_ingest_json`.

**Do not** add HubSpot “Create contact” or “Update deal” actions on this table.

## Table B — New hires at account (buyer / champion)

**Input rows**: One row per **target account** (`account_domain` from pilot segment).

| Column | Type | Purpose |
|--------|------|---------|
| `account_domain` | Text | Primary key for account |
| `account_name` | Text | |
| `hs_company_id` | Text | HubSpot company lookup |
| `buyer_title_keywords` | Text | Default: `VP,Director,Head,Chief,Partner,Principal` |
| `champion_title_keywords` | Text | Default: `RevOps,GTM,Marketing Ops,Demand Gen` |

Run **Find People at Company** (or new-hire provider) with title filters → child table or expanded rows:

| Column | Type | Purpose |
|--------|------|---------|
| `person_full_name` | Text | |
| `person_linkedin_url` | URL | Required for new_hire |
| `person_work_email` | Email | Optional |
| `current_title` | Text | |
| `start_date` | Date | If provider supplies |
| `buyer_champion_match` | Formula | Title matches keyword lists |
| `signal_type` | Text | constant `new_hire` |
| `detected_at` | Date | `start_date` or run date |
| `confidence_score` | Number | |
| `emit_signal` | Formula | buyer_champion_match AND confidence ≥ 0.5 |
| `signal_ingest_json` | Formula | ingest body; `company_domain` = `account_domain` |

Webhook: same ingest URL as Table A.

## Pilot segment filter

Apply at source import (HubSpot list or Clay filter):

- Industry / segment: PE, private credit (your HS property names).
- Deal created date ≥ rolling 12 months.
- Exclude test accounts.

## CLI alternative (no live webhook)

Export table CSV →:

```bash
python3 signal_engine/scripts/map_clay_row_to_signal.py \
  --input ~/Downloads/signal_engine_commercial_v1.csv \
  --table-id signal_engine_commercial_v1 \
  --output /tmp/signals.jsonl
```

Then batch POST with `dry_run_ingest.sh` or your orchestrator.

## Checklist

- [ ] New table created (not RB2B `t_0t6nmvhh4tbjH6sKTWd`)
- [ ] HubSpot columns are lookup-only
- [ ] `signal_ingest_json` validates against schema
- [ ] Table webhook or HTTP POST points to ingest URL with server-side auth
- [ ] Sample rows tested with [samples](../samples/)
