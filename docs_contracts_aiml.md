# AI/ML Service Contract

**Owner:** Person B
**Status:** ✅ Live — tested end-to-end (extraction, exact-duplicate, fuzzy-duplicate)
**Base URL (local dev):** `http://localhost:8001`
**Base URL (deployed):** _fill in once hosted — update this line and ping the team_

> Backend: set `AIML_SERVICE_URL` to whichever URL above is current for your environment.

---

## `POST {AIML_SERVICE_URL}/extract`

**Request:** `multipart/form-data`

| field  | type | required | notes                                                              |
|--------|------|----------|---------------------------------------------------------------------|
| `file` | file | yes      | PDF, PNG, JPG, JPEG, TIF, TIFF, BMP, or WEBP. Max 20MB.             |

**Success response — `200 OK`**

```json
{
  "owner_name": "Ramesh Kumar Verma",
  "plot_number": "PLT-2291",
  "survey_number": "SUR-114-A",
  "address": "22 MG Road, Sector 9, Pune, Maharashtra",
  "area_sqft": 1450.0,
  "registration_date": "2019-03-14",
  "confidence_score": 0.981,
  "duplicate_flag": false,
  "duplicate_matches": [
    { "plot_number": "PLT-2291X", "similarity_score": 0.965 }
  ]
}
```

**Field notes for Backend:**

- Any of `owner_name` / `plot_number` / `survey_number` / `address` / `area_sqft` / `registration_date` can come back as `null` if that field wasn't found in the document — **the request still succeeds** (design choice: a partial extraction with a low `confidence_score` is more useful than a hard failure). Backend should not assume these are always populated.
- `confidence_score` is a float `0.0`–`1.0`. Suggested Backend behaviour: treat `< 0.5` as "needs manual review" rather than auto-verifying.
- `duplicate_flag: true` means an (near-)exact plot number match was found — Backend should likely block blockchain registration in this case, or route to manual review.
- `duplicate_flag: false` with a non-empty `duplicate_matches` array means a *partial* match was found (e.g. a typo'd plot number) — worth surfacing to the Frontend as a warning even though it's not an outright block.
- `duplicate_matches` is always present (empty array `[]` if no matches), never `null`.

**Error responses:**

| status | when                                              | body                                                        |
|--------|---------------------------------------------------|---------------------------------------------------------------|
| `400`  | missing file, empty file, unsupported extension, file >20MB | `{ "detail": "<readable message>" }`                        |
| `422`  | OCR/parsing failed or no readable text found      | `{ "detail": "<readable message>" }`                        |

Backend should treat both as "this document couldn't be processed" and surface `detail` to the Frontend rather than retrying blindly.

---

## `GET {AIML_SERVICE_URL}/health`

Liveness/readiness check — useful for Backend to confirm the AI/ML service is up (and has its OCR dependency installed) before routing traffic to it.

```json
{ "status": "ok", "tesseract_available": true, "records_stored": 4 }
```

If `tesseract_available: false`, the service is up but will fail every `/extract` call — treat as not-ready.

---

## Change log

_Log any change to the shapes above here, with a timestamp, so nobody has to guess what changed._

| Date | Change | By |
|------|--------|-----|
| _(hackathon start)_ | Initial contract published, matches SRS exactly | Person B |
