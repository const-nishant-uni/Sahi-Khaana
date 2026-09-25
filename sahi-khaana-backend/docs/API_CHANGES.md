# Backend API changes: checklist for the Flutter developer

Backend frozen at tag **`v1.0-backend`**. This file lists everything that differs from the Phase 1 mock
you may have started from, then documents every endpoint, field, warning and error code.
Interactive docs (Swagger) are at `http://<host>:8000/docs` while the server runs.

> **After pulling: delete your local `sahi_khaana.db`** (in the `sahi-khaana-backend` folder). The database
> schema changed several times (explanation columns, nullable finding ids, the `repaired` column) and existing
> tables are not migrated. The file is recreated on the next start.

Base URL: `http://<host>:8000/api/v1`. On an Android emulator use `http://10.0.2.2:8000/api/v1`
(`10.0.2.2` is the emulator's name for your computer). Plain HTTP on Android needs
`android:usesCleartextTraffic="true"` in the manifest (development only).

---

## 1. Checklist: what to change

**Requests**
- [ ] Send the header `X-Device-Id: <uuid>` on `/scan`, `/analyze` and every `/scans*` call. Generate a UUID once, store it on the device, reuse it. Missing header gives 400 `MISSING_DEVICE_ID`; a non-UUID gives 400 `INVALID_DEVICE_ID`. (`/health`, `/categories` and `/mock/scan` don't need it.)
- [ ] `POST /scan` is `multipart/form-data`: file field **`image`** (JPG, PNG or WEBP, at most 5 MB) and optional text field **`food_category`** (an `id` from `GET /categories`).
- [ ] Use `GET /categories` for the food-category dropdown and send the chosen `id`. An unknown id gives 400 `INVALID_CATEGORY`.

**New endpoints** (details in section 2)
- [ ] `POST /analyze`: same analysis from typed text, no photo.
- [ ] `GET /scans`, `GET /scans/{scan_id}`, `DELETE /scans/{scan_id}`: history for this device.
- [ ] `GET /scans/{scan_id}/explanation`: plain-English explanation.

**Response fields**
- [ ] `health_result.data_completeness` is now a **string** (`"full"`, `"partial"` or `"ingredients_only"`). It used to be a number. The number now lives in the new field `health_result.completeness_score` (0 to 1).
- [ ] `fssai_result.findings[].ingredient_id` can be **`null`**: a label-level finding (currently: a required declaration was not found). Show it as a note about the whole label, not under an ingredient.
- [ ] **New** `ingredients[].repaired` (boolean): `true` when the OCR ran words together (`Refinedwheatflour`) and the backend recovered the match by splitting them. `ingredients[].original` is always the raw OCR token as read; `normalized` is the matched name. Consider showing `normalized` when `repaired` is true.
- [ ] `fssai_result.summary` counts ingredients only (`pass + flag + review == scanned` always). Label-level findings are not counted there, but they can make `overall_status` `REVIEW`.
- [ ] `ingredients[].ins_number` is filled from the rule data even if the label printed only the name.
- [ ] The summary counter's JSON key is `"pass"` (a Dart-friendly name such as `passCount` is up to you).
- [ ] `warnings` is now a real list (section 4). The Phase 1 `MOCK_DATA` warning **no longer appears**; remove any UI for it.
- [ ] `GET /mock/scan` matches the final shape (including a `null` finding id and one `repaired` ingredient). Use it for layout work.

**Errors** (full table in section 5)
- [ ] Always `{"error": {"code": "...", "message": "..."}}`. Switch on `code`, not on the message text.
- [ ] New codes: `MISSING_DEVICE_ID`, `INVALID_DEVICE_ID`, `INVALID_CATEGORY`, `SCAN_NOT_FOUND`, `VALIDATION_ERROR`, plus generic `NOT_FOUND`, `METHOD_NOT_ALLOWED`, `HTTP_ERROR`, `INTERNAL_ERROR`.

**Behaviour**
- [ ] Expect mostly `REVIEW` for anything containing additives for now (see section 6).
- [ ] The first call to `/explanation` for a scan can take a few seconds. Show a spinner.
- [ ] Show `LIMITED_NUTRITION_DATA` next to the health score, and `data_completeness` somewhere visible.

---

## 2. Endpoints

| Method and path | Needs `X-Device-Id` | Body / query | Success |
|---|---|---|---|
| `GET /health` | no | none | 200 `{"status": "ok", "version": "..."}` |
| `GET /categories` | no | none | 200 `{"categories": [{"id": "bakery", "name": "Bread, biscuits & bakery"}, ...]}` |
| `POST /scan` | yes | multipart: `image`, optional `food_category` | 200 scan object (section 3) |
| `POST /analyze` | yes | JSON, see below | 200 scan object, `ocr` is `null` |
| `GET /scans` | yes | `limit` (1-100, default 20), `offset` (default 0) | 200 `{"items": [...], "total", "limit", "offset"}` |
| `GET /scans/{scan_id}` | yes | none | 200 scan object |
| `DELETE /scans/{scan_id}` | yes | none | **204, empty body** |
| `GET /scans/{scan_id}/explanation` | yes | none | 200 `{"explanation": "...", "source": "llm" or "template"}` |
| `GET /mock/scan` | no | none | 200 sample scan object |

`POST /analyze` JSON body (send `ingredients_text` **or** `ingredients`; the rest is optional):

```json
{
  "ingredients_text": "Wheat flour (72%), Salt, Preservative (INS 211)",
  "ingredients": ["Wheat flour (72%)", "Salt"],
  "nutrition_text": "per 100 g: Total sugars 3.4 g, Sodium 900 mg",
  "food_category": "bakery"
}
```
Limits: `ingredients_text` 5000 characters, `ingredients` 100 items, `nutrition_text` 3000 characters. A whole pasted label ("Ingredients: ... Nutrition: ...") also works.

`GET /scans` returns newest first, only this device's scans. `total` is all scans for the device (keep paging while `offset + items.length < total`). An empty history is `{"items": [], "total": 0, ...}`, not an error. `GET`/`DELETE` of an unknown id **or another device's id** both give 404 `SCAN_NOT_FOUND`; deleting twice gives 404 the second time.

`GET /scans/{id}/explanation`: `"llm"` = worded by an AI from the rule results; `"template"` = built directly from them (no API key, or the AI call failed). It never changes any status. An `"llm"` answer is cached (later calls are instant). A template produced because the AI *failed* is not cached, so a later call tries again.

---

## 3. The scan object (`/scan`, `/analyze`, `GET /scans/{id}`)

| Field | Type | Notes |
|---|---|---|
| `scan_id` | string (UUID) | |
| `created_at` | string | ISO-8601, UTC |
| `status` | `"ok"` | always |
| `warnings` | string[] | section 4; may be empty |
| `ocr` | object or `null` | `null` for `/analyze`. `{raw_text, confidence 0-1, engine}` (`engine` is `rapidocr`, `rapidocr-original` or `tesseract`) |
| `food_category` | string or `null` | the id you sent |
| `ingredients[]` | object | see below |
| `nutrition` | object | every value can be `null` |
| `fssai_result` | object | see below |
| `health_result` | object | see below |

**`ingredients[]`**: `id` (`"ing_1"`...), `original` (raw OCR token), `normalized` (matched name or `null`), `category` (or `null`), `ins_number` (or `null`), `percentage` (or `null`), `match_confidence` (0-1), `known` (bool: found in the rule data), **`repaired`** (bool).

**`nutrition`**: `basis` (`"per_100g"`, `"per_100ml"`, `"per_serving"` or `null`), `energy_kcal`, `sugar_g`, `sodium_mg`, `sat_fat_g`, `trans_fat_g`, `total_fat_g`, `protein_g`, `fiber_g` (numbers or `null`; energy is always kcal, sodium always mg).

**`fssai_result`**
- `overall_status`: `"PASS"`, `"FLAG"` or `"REVIEW"`. Any FLAG gives FLAG; otherwise any REVIEW (ingredient or label-level) gives REVIEW; otherwise PASS.
- `summary`: `{scanned, matched, pass, flag, review}` (ingredient counts).
- `confidence`: 0-1 (OCR confidence x share of ingredients recognised).
- `findings[]`: `{ingredient_id (string or null), rule_id, status, reason, source}`. One per ingredient, plus one per missing declaration with `ingredient_id: null` and reason `"Declaration not found in the scanned area"`. `source` says where the rule comes from; entries beginning `TODO:` are unverified.

**`health_result`**: `score` (0-100), `assessment` (`"FEWER CONCERNS"`, `"MODERATE"` or `"SEVERAL CONCERNS"`), `data_completeness` (`"full"`, `"partial"`, `"ingredients_only"`), `completeness_score` (0-1), `factors[]` (`{key, type: "nutrient" or "ingredient", impact (points, negative = concern), label, detail}`), `disclaimer` (show it).

**`GET /scans` item**: `scan_id`, `created_at`, `food_category` (or `null`), `overall_status`, `health_score`, `assessment`, `ingredient_count`.

A repaired ingredient (from `/analyze` with `"Refinedwheatflour (72%)"`):

```json
{
  "id": "ing_1",
  "original": "Refinedwheatflour (72%)",
  "normalized": "wheat flour",
  "category": "cereal",
  "ins_number": null,
  "percentage": 72.0,
  "match_confidence": 1.0,
  "known": true,
  "repaired": true
}
```

---

## 4. Warnings (`warnings[]`)

| Warning | Meaning | Suggested UI |
|---|---|---|
| `LOW_OCR_CONFIDENCE` | OCR confidence is below 0.75; the text may contain mistakes | "Photo was hard to read, please check" |
| `NO_NUTRITION_FOUND` | No nutrient values were found on the label | Hide/gray the nutrition section |
| `IMPLAUSIBLE_NUTRIENT_IGNORED:<field>` | A value was dropped as an obvious OCR error, e.g. `IMPLAUSIBLE_NUTRIENT_IGNORED:total_fat_g` | Optional note |
| `LIMITED_NUTRITION_DATA` | No usable per-100 g nutrition. The score is based on ingredients only and the assessment is **capped at `MODERATE`** | Show next to the health score |
| `NUTRITION_PER_SERVING_ONLY` | Only a per-serving table was found; it is not scored (`LIMITED_NUTRITION_DATA` is added too) | "Only per-serving values found" |

Warnings can carry a suffix after a colon; match on the part before it.

---

## 5. Error codes

Body is always `{"error": {"code": "...", "message": "..."}}`. The `message` is for logs; show your own text per `code`.

| HTTP | `code` | When |
|---|---|---|
| 400 | `MISSING_DEVICE_ID` | `X-Device-Id` header missing |
| 400 | `INVALID_DEVICE_ID` | `X-Device-Id` is not a UUID |
| 400 | `INVALID_FILE` | No `image` field, empty file, or not JPG/PNG/WEBP (checked by content, not file name) |
| 400 | `INVALID_CATEGORY` | `food_category` is not an id from `GET /categories` |
| 404 | `SCAN_NOT_FOUND` | No scan with that id for this device |
| 404 | `NOT_FOUND` | Unknown URL |
| 405 | `METHOD_NOT_ALLOWED` | Wrong HTTP method for the URL |
| 413 | `FILE_TOO_LARGE` | Image over 5 MB |
| 422 | `POOR_IMAGE` | Photo too blurry to read: ask for a retake |
| 422 | `NO_TEXT_FOUND` | No text could be read: ask for a retake |
| 422 | `NO_INGREDIENTS_SECTION` | Text was read but no ingredients list was found (also `/analyze` with nothing parseable): ask the user to photograph the ingredients panel |
| 422 | `VALIDATION_ERROR` | Bad JSON body or query value (e.g. neither `ingredients_text` nor `ingredients`, `limit=0`) |
| other | `HTTP_ERROR` | Any other HTTP error status |
| 500 | `INTERNAL_ERROR` | Server bug |

---

## 6. Behaviour notes

- **Additives will mostly be `REVIEW` for now.** The rule data for additives is a set of unverified placeholders, so the engine deliberately never says PASS or FLAG for an additive until real conditions are filled in. Plain foods (flour, sugar, salt, oils) come out `PASS`. Don't design around many `FLAG` results yet.
- **`overall_status` can be `REVIEW` while `summary.review` is 0**, if a label-level finding exists. Explain it with that finding's `reason`.
- **`health_result.assessment` is capped at `MODERATE`** whenever there is no usable per-100 g nutrition data, even if the score is high. Nutrition tables per 100 ml (drinks) are scored with half the thresholds.
- **Missing nutrients are `null`, never 0.**
- **Typed text (`/analyze`) has no OCR**, so `ocr` is `null` and `fssai_result.confidence` is not reduced by OCR quality.
- **Stored photos older than 7 days are deleted when the server starts.** The scan and its result stay in history; the API never returns the photo itself.
- **Speed:** a scan takes about 2 to 4 seconds (mostly OCR). Use a generous timeout (30 s) and a progress indicator.
- **Identity:** there is no login. The device id is the only key, so reinstalling the app (new id) loses access to old history.
- **All statuses come from fixed rules, never from AI.** The explanation text may be AI-worded but cannot change a status.
- **CORS** is open to all origins (development setting).

---

## 7. Example: `POST /scan`

Request: `image` = a label photo, `food_category=cereals_noodles`, header `X-Device-Id: 3f0c2c5e-8a4b-4c6f-9d1e-2b7a5e9c1d34`.
This is real output for the synthetic label `tests/fixtures/eval/example_1.jpg` (ids and timestamps vary per call).

```json
{
  "scan_id": "6e50b23f-d4c0-41b4-8793-e0ba8c61c2b8",
  "created_at": "2026-09-25T11:03:54.997690+00:00",
  "status": "ok",
  "warnings": [],
  "ocr": {
    "raw_text": "INGREDIENTS: Refined wheat flour (72%), Palm oil, Salt, Sugar,\nAcidity regulator (INS 501(i) ), Flavour enhancer (INS 627,\nINS631),Colour\uff08INS102),Preservative\uff08INS211).\nNUTRITION INFORMATION per 100g: Energy452kcal,\nTotal fat 17.5 g, Saturated fat 8.2 g, Trans fat 0.1 g.\nTotal sugars 3.4 g, Protein 9.1 g, Sodium 1240 mg",
    "confidence": 0.9513,
    "engine": "rapidocr"
  },
  "food_category": "cereals_noodles",
  "ingredients": [
    {
      "id": "ing_1",
      "original": "Refined wheat flour (72%)",
      "normalized": "wheat flour",
      "category": "cereal",
      "ins_number": null,
      "percentage": 72.0,
      "match_confidence": 1.0,
      "known": true,
      "repaired": false
    },
    {
      "id": "ing_2",
      "original": "Palm oil",
      "normalized": "palm oil",
      "category": "fat_oil",
      "ins_number": null,
      "percentage": null,
      "match_confidence": 1.0,
      "known": true,
      "repaired": false
    },
    {
      "id": "ing_3",
      "original": "Salt",
      "normalized": "salt",
      "category": "seasoning",
      "ins_number": null,
      "percentage": null,
      "match_confidence": 1.0,
      "known": true,
      "repaired": false
    },
    {
      "id": "ing_4",
      "original": "Sugar",
      "normalized": "sugar",
      "category": "sugar",
      "ins_number": null,
      "percentage": null,
      "match_confidence": 1.0,
      "known": true,
      "repaired": false
    },
    {
      "id": "ing_5",
      "original": "Acidity regulator (INS 501(i))",
      "normalized": "potassium carbonate",
      "category": "acidity_regulator",
      "ins_number": "501(i)",
      "percentage": null,
      "match_confidence": 1.0,
      "known": true,
      "repaired": false
    },
    {
      "id": "ing_6",
      "original": "Flavour enhancer (INS 627)",
      "normalized": "disodium guanylate",
      "category": "flavour_enhancer",
      "ins_number": "627",
      "percentage": null,
      "match_confidence": 1.0,
      "known": true,
      "repaired": false
    },
    {
      "id": "ing_7",
      "original": "Flavour enhancer (INS 631)",
      "normalized": "disodium inosinate",
      "category": "flavour_enhancer",
      "ins_number": "631",
      "percentage": null,
      "match_confidence": 1.0,
      "known": true,
      "repaired": false
    },
    {
      "id": "ing_8",
      "original": "Colour (INS 102)",
      "normalized": "tartrazine",
      "category": "colour",
      "ins_number": "102",
      "percentage": null,
      "match_confidence": 1.0,
      "known": true,
      "repaired": false
    },
    {
      "id": "ing_9",
      "original": "Preservative (INS 211)",
      "normalized": "sodium benzoate",
      "category": "preservative",
      "ins_number": "211",
      "percentage": null,
      "match_confidence": 1.0,
      "known": true,
      "repaired": false
    }
  ],
  "nutrition": {
    "basis": "per_100g",
    "energy_kcal": null,
    "sugar_g": 3.4,
    "sodium_mg": 1240.0,
    "sat_fat_g": 8.2,
    "trans_fat_g": 0.1,
    "total_fat_g": 17.5,
    "protein_g": 9.1,
    "fiber_g": null
  },
  "fssai_result": {
    "overall_status": "REVIEW",
    "summary": {
      "scanned": 9,
      "matched": 9,
      "pass": 4,
      "flag": 0,
      "review": 5
    },
    "confidence": 0.9513,
    "findings": [
      {
        "ingredient_id": "ing_1",
        "rule_id": "wheat_flour",
        "status": "PASS",
        "reason": "wheat flour is permitted.",
        "source": "General food ingredient (not an additive). TODO: verify against FSS (FPS&FA) Regulations 2011"
      },
      {
        "ingredient_id": "ing_2",
        "rule_id": "palm_oil",
        "status": "PASS",
        "reason": "palm oil is permitted.",
        "source": "General food ingredient (not an additive). TODO: verify against FSS (FPS&FA) Regulations 2011"
      },
      {
        "ingredient_id": "ing_3",
        "rule_id": "salt",
        "status": "PASS",
        "reason": "salt is permitted.",
        "source": "General food ingredient (not an additive). TODO: verify against FSS (FPS&FA) Regulations 2011"
      },
      {
        "ingredient_id": "ing_4",
        "rule_id": "sugar",
        "status": "PASS",
        "reason": "sugar is permitted.",
        "source": "General food ingredient (not an additive). TODO: verify against FSS (FPS&FA) Regulations 2011"
      },
      {
        "ingredient_id": "ing_5",
        "rule_id": "ins_501_i",
        "status": "REVIEW",
        "reason": "No verified rule for potassium carbonate in category 'cereals_noodles'.",
        "source": "TODO: verify against FSS (FPS&FA) Regulations 2011 (placeholder status; name/INS only from the Codex INS list)"
      },
      {
        "ingredient_id": "ing_6",
        "rule_id": "ins_627",
        "status": "REVIEW",
        "reason": "No verified rule for disodium guanylate in category 'cereals_noodles'.",
        "source": "TODO: verify against FSS (FPS&FA) Regulations 2011 (placeholder status; name/INS only from the Codex INS list)"
      },
      {
        "ingredient_id": "ing_7",
        "rule_id": "ins_631",
        "status": "REVIEW",
        "reason": "No verified rule for disodium inosinate in category 'cereals_noodles'.",
        "source": "TODO: verify against FSS (FPS&FA) Regulations 2011 (placeholder status; name/INS only from the Codex INS list)"
      },
      {
        "ingredient_id": "ing_8",
        "rule_id": "ins_102",
        "status": "REVIEW",
        "reason": "No verified rule for tartrazine in category 'cereals_noodles'.",
        "source": "TODO: verify against FSS (FPS&FA) Regulations 2011 (placeholder status; name/INS only from the Codex INS list)"
      },
      {
        "ingredient_id": "ing_9",
        "rule_id": "ins_211",
        "status": "REVIEW",
        "reason": "No verified rule for sodium benzoate in category 'cereals_noodles'.",
        "source": "TODO: verify against FSS (FPS&FA) Regulations 2011 (placeholder status; name/INS only from the Codex INS list)"
      },
      {
        "ingredient_id": null,
        "rule_id": "DECL-COLOUR-001",
        "status": "REVIEW",
        "reason": "Declaration not found in the scanned area",
        "source": "TODO: verify against FSS (FPS&FA) Regulations 2011"
      }
    ]
  },
  "health_result": {
    "score": 60,
    "assessment": "MODERATE",
    "data_completeness": "full",
    "completeness_score": 0.88,
    "factors": [
      {
        "key": "medium_total_fat",
        "type": "nutrient",
        "impact": -5.0,
        "label": "Medium total fat",
        "detail": "More than 3 g total fat per 100 g (this product: 17.5 g total fat)."
      },
      {
        "key": "high_sat_fat",
        "type": "nutrient",
        "impact": -15.0,
        "label": "High saturated fat",
        "detail": "More than 5 g saturated fat per 100 g (this product: 8.2 g saturated fat)."
      },
      {
        "key": "high_sodium",
        "type": "nutrient",
        "impact": -20.0,
        "label": "High sodium",
        "detail": "More than 600 mg sodium (1.5 g salt) per 100 g (this product: 1240 mg sodium)."
      }
    ],
    "disclaimer": "General information only. Not medical or dietary advice."
  }
}
```

## 8. Example: `GET /scans`

Two scans for one device (the first is the newer `/analyze` scan, the second the `/scan` above):

```json
{
  "items": [
    {
      "scan_id": "245ea2b5-d6b2-434f-8766-bd04c76bcb9c",
      "created_at": "2026-09-25T11:03:55.010033+00:00",
      "food_category": "bakery",
      "overall_status": "PASS",
      "health_score": 90,
      "assessment": "FEWER CONCERNS",
      "ingredient_count": 3
    },
    {
      "scan_id": "6e50b23f-d4c0-41b4-8793-e0ba8c61c2b8",
      "created_at": "2026-09-25T11:03:54.997690+00:00",
      "food_category": "cereals_noodles",
      "overall_status": "REVIEW",
      "health_score": 60,
      "assessment": "MODERATE",
      "ingredient_count": 9
    }
  ],
  "total": 2,
  "limit": 20,
  "offset": 0
}
```

## 9. Example: `GET /scans/{scan_id}/explanation`

```json
{
  "explanation": "FSSAI rule check: REVIEW. Of 9 ingredients, 4 passed, 0 were flagged and 5 need review. Needs review: No verified rule for potassium carbonate in category 'cereals_noodles'; No verified rule for disodium guanylate in category 'cereals_noodles' (and 3 more). A required declaration was not found in the scanned area, so check the pack itself. Health view: score 60/100, moderate. Main factors: Medium total fat, High saturated fat, High sodium. This is general information, not medical or compliance advice.",
  "source": "template"
}
```
