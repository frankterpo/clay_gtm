# Signal Engine PoC v1 — Clay (commercial external signals)

Clay is the **primary external** source for `job_change`, `promotion`, and `new_hire` in the append-only signals pipeline. HubSpot writes are **out of scope here** (Dagster + `SKIP_EXISTING_HS` owns CRM updates).

**Do not use** the RB2B Clay table `t_0t6nmvhh4tbjH6sKTWd`. Use a dedicated workbook/table (recipe below).

## Layout

| Path | Purpose |
|------|---------|
| [clay/table-recipe.md](clay/table-recipe.md) | Clay columns, enrichments, webhook wiring |
| [docs/clay-to-signals-mapping.md](docs/clay-to-signals-mapping.md) | Clay → unified ingest field mapping |
| [schemas/clay-signal-ingest.schema.json](schemas/clay-signal-ingest.schema.json) | Producer contract (JSON Schema) |
| [samples/](samples/) | Three dry-run payloads (`job_change`, `promotion`, `new_hire`) |
| [scripts/map_clay_row_to_signal.py](scripts/map_clay_row_to_signal.py) | Map Clay CSV export → ingest JSON |
| [scripts/validate_payload.py](scripts/validate_payload.py) | Validate JSON against schema |
| [scripts/dry_run_ingest.sh](scripts/dry_run_ingest.sh) | POST sample to ingest URL (no HS) |

## Quick start

```bash
# Validate samples
python3 signal_engine/scripts/validate_payload.py signal_engine/samples/*.dry.json

# Map a Clay export (see clay/table-recipe.md for column names)
python3 signal_engine/scripts/map_clay_row_to_signal.py \
  --input path/to/clay_export.csv \
  --output /tmp/signals.jsonl

# Dry-run POST (set INGEST_URL + auth; does not touch HubSpot)
export INGEST_URL="https://YOUR_PROJECT.supabase.co/functions/v1/signal-ingest"
export INGEST_BEARER="YOUR_SERVICE_ROLE_OR_FUNCTION_SECRET"
./signal_engine/scripts/dry_run_ingest.sh signal_engine/samples/job_change.dry.json
```

## Ingest targets (pick one)

Documented in [docs/clay-to-signals-mapping.md](docs/clay-to-signals-mapping.md#ingest-endpoints):

1. **Supabase Edge Function** `signal-ingest` (recommended): validates body, inserts into `signals` with service role on the server only.
2. **Supabase REST** `POST /rest/v1/signals` with `apikey` + `Authorization: Bearer <service_role>` — PoC only; prefer Edge Function for validation and secrets.

Clay should **POST the unified JSON body** from a formula column or HTTP API action — not HubSpot create/update actions.
