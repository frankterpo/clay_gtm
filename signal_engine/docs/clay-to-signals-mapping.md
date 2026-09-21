# Clay fields → signals ingest mapping

Target row shape matches the Signal Engine PoC brief (append-only `signals` table). Clay is **`source: clay`** only for this doc.

## Ingest endpoints

### Option A — Edge Function (recommended)

| Item | Value |
|------|--------|
| Method | `POST` |
| URL | `https://<project_ref>.supabase.co/functions/v1/signal-ingest` |
| Headers | `Content-Type: application/json`, `Authorization: Bearer <SUPABASE_SERVICE_ROLE or function-specific secret>` |
| Body | Single object per request (schema below) |

Server responsibilities: JSON Schema validation, idempotency on `idempotency_key`, insert into `signals`, **no HubSpot API calls** in PoC.

### Option B — Supabase REST (PoC / internal only)

| Item | Value |
|------|--------|
| Method | `POST` |
| URL | `https://<project_ref>.supabase.co/rest/v1/signals` |
| Headers | `apikey: <service_role>`, `Authorization: Bearer <service_role>`, `Content-Type: application/json`, `Prefer: return=minimal` |
| Body | Map ingest JSON columns to DB columns (see table) |

**Never** embed `service_role` in Clay. Use a Clay **Secrets** field or proxy through the Edge Function.

## DB column mapping (ingest JSON → `signals`)

| DB / brief field | Ingest JSON field | Notes |
|------------------|-------------------|--------|
| `signal_id` | `signal_id` | Optional; DB default `gen_random_uuid()` or `sig_*` generator |
| `detected_at` | `detected_at` | ISO-8601 UTC |
| `signal_type` | `signal_type` | `job_change` \| `promotion` \| `new_hire` |
| `source` | `source` | Always `clay` |
| `hubspot_contact_id` | `hubspot_contact_id` | From Clay HubSpot **lookup** column (read) |
| `hubspot_company_id` | `hubspot_company_id` | Lookup on `company_domain` |
| `hubspot_deal_id` | `hubspot_deal_id` | Optional open deal lookup |
| `record_state` | `record_state` | From HS workflow export or leave null for pipeline to compute |
| `payload` | `payload` | JSONB: titles, domains, person keys, Clay metadata |
| `confidence` | `confidence` | 0–1 |
| `status` | `status` | Default `new` |
| `actioned_by` | — | Set by downstream automations, not Clay |

Unique constraint (suggested): `(source, idempotency_key)`.

## Clay column → ingest JSON

Clay column names are from [clay/table-recipe.md](../clay/table-recipe.md). Formula column **`signal_ingest_json`** should stringify the object Clay POSTs.

| Clay column | Ingest path | Transform |
|-------------|-------------|-----------|
| `signal_type` | `signal_type` | Enum; see classification |
| `detected_at` | `detected_at` | `{{Detected At}}` or enrichment timestamp → ISO UTC |
| `confidence_score` | `confidence` | Number 0–1 |
| `hs_contact_id` | `hubspot_contact_id` | String; empty → omit/null |
| `hs_company_id` | `hubspot_company_id` | String |
| `hs_deal_id` | `hubspot_deal_id` | Optional |
| `record_state` | `record_state` | From synced HS field if available |
| `person_work_email` | `payload.person_email` | Lowercase trim |
| `person_linkedin_url` | `payload.person_linkedin_url` | Normalize `https://www.linkedin.com/in/...` |
| `person_full_name` | `payload.person_full_name` | |
| `account_domain` | `payload.company_domain` | Apex domain, no `www` |
| `account_name` | `payload.company_name` | |
| `previous_title` | `payload.old_title` | |
| `current_title` | `payload.new_title` | |
| `previous_company_domain` | `payload.old_company_domain` | job_change |
| `previous_company_name` | `payload.old_company_name` | |
| `current_company_domain` | `payload.new_company_domain` | job_change |
| `current_company_name` | `payload.new_company_name` | |
| `buyer_champion_match` | `payload.buyer_champion_match` | Boolean formula |
| `clay_table_id` | `payload.clay_table_id` | Constant per table |
| `clay_row_id` | `payload.clay_row_id` | `{{Row ID}}` |
| `enrichment_provider` | `payload.clay_enrichment_provider` | e.g. `mixrank_job_change` |
| `idempotency_key` | `idempotency_key` | Formula: `clay:{{table}}:{{row}}:{{signal_type}}:{{date}}` |

Always set top-level `"source": "clay"`.

## Signal type classification (Clay formulas)

| `signal_type` | Rule |
|---------------|------|
| `new_hire` | Table source = **New hires at account** OR `is_new_hire_at_account` = true |
| `job_change` | `previous_company_domain` ≠ `current_company_domain` (both non-empty) |
| `promotion` | Same `current_company_domain` as `previous_company_domain` (or single employer) AND `previous_title` ≠ `current_title` |

Run classification **before** webhook emit; only rows with `emit_signal` = true should POST.

## Confidence heuristics (Clay)

| Score | Condition |
|-------|-----------|
| 0.9+ | Provider flag “confirmed” + LinkedIn URL + domain match |
| 0.75 | Provider job change + work email on same domain |
| 0.6 | Title/company change without email |
| 0.5 | New hire from “Find People” only (no HS contact yet) |

## HubSpot in Clay (read-only)

Allowed:

- **Find contact by email** / **Find company by domain** → populate `hs_*` columns.

Not allowed in PoC:

- Create/update contact, company, or deal from Clay.
- Dual-write to HubSpot CRM objects.

## Webhook POST body (Clay)

Use **Table webhook** (on row create/update when `emit_signal` is true) or **HTTP API** action with body = `{{signal_ingest_json}}`.

Example minimal POST:

```json
{
  "source": "clay",
  "signal_type": "job_change",
  "detected_at": "2026-09-17T14:22:00Z",
  "confidence": 0.82,
  "hubspot_contact_id": "10234",
  "hubspot_company_id": "55871",
  "idempotency_key": "clay:signal_engine_commercial_v1:row_abc:job_change:2026-09-17",
  "payload": {
    "person_email": "jane.doe@newco.com",
    "person_linkedin_url": "https://www.linkedin.com/in/janedoe",
    "company_domain": "newco.com",
    "old_title": "VP Marketing",
    "new_title": "CMO",
    "old_company_domain": "oldco.com",
    "new_company_domain": "newco.com"
  }
}
```

Validate with:

```bash
python3 signal_engine/scripts/validate_payload.py path/to/payload.json
```
