# Sahi Khaana - Backend

FastAPI backend for the Sahi Khaana Flutter app. A user photographs a packaged
food's ingredient label; the backend preprocesses the image (OpenCV), reads it
(OCR), extracts ingredients and nutrition, applies **deterministic** FSSAI rules
(PASS / FLAG / REVIEW) and a configurable health assessment, and returns JSON.

> Principle: OCR/AI extracts information; deterministic rules make the
> regulatory decision. An LLM only phrases explanations, never decides.

## Status: Phase 3 (engines + database)

| Part | State |
|---|---|
| Upload validation, preprocessing, OCR (RapidOCR + Tesseract fallback) | real |
| Section finding, `ingredients`, `nutrition`, `POST /analyze` | real |
| FSSAI rule engine, health engine | real (but the **rule data is placeholder**, see "Rule data") |
| SQLite history: `GET /scans`, `GET /scans/{id}`, `DELETE /scans/{id}` | real |
| LLM explanation, image cleanup, evaluation script | not built yet (Phase 4) |

`GET /api/v1/mock/scan` returns a complete, realistic sample of the final response.

**`X-Device-Id` (a UUID) is required** on `/scan`, `/analyze` and `/scans*`. It scopes history: a device can only see and delete its own scans (another device's scan id returns 404).

## Setup

Requires Python 3.11.

```bash
python -m venv .venv            # or use your conda env
source .venv/bin/activate       # Windows: .venv\Scripts\activate

pip install -r requirements.txt
# rapidocr-onnxruntime must be installed WITHOUT deps: it pulls in the full
# "opencv-python", which conflicts with opencv-python-headless.
pip install rapidocr-onnxruntime --no-deps

cp .env.example .env            # Windows: copy .env.example .env
```

### Tesseract (fallback OCR engine)

Only used when RapidOCR is unsure. The app still runs without it (the fallback
is skipped and a warning is logged).

- **Linux (Debian/Ubuntu):** `sudo apt install tesseract-ocr`
- **Linux (Arch):** `sudo pacman -S tesseract tesseract-data-eng`
- **Windows:** install from https://github.com/UB-Mannheim/tesseract/wiki, then
  add the install folder (e.g. `C:\Program Files\Tesseract-OCR`) to `PATH`.
  Check with `tesseract --version`.

## Run

```bash
uvicorn app.main:app --reload --host 0.0.0.0
```

- Swagger UI: http://localhost:8000/docs
- The SQLite file `sahi_khaana.db` is created on first start (gitignored). If you ran an earlier Phase 3 build, **delete it once**: the `findings` table now allows a null `ingredient_id`, and existing tables are not migrated.
- The first start takes a few seconds (OCR models load once at startup).

### Connecting the Flutter app

| Client | Base URL |
|---|---|
| Android emulator | `http://10.0.2.2:8000/api/v1` |
| iOS simulator | `http://localhost:8000/api/v1` |
| Physical phone (same Wi-Fi) | `http://<your-PC-LAN-IP>:8000/api/v1` |

`10.0.2.2` is how the Android emulator reaches your computer's `localhost`.
Every request should send `X-Device-Id: <uuid>` (generate once, store on device).
Plain-HTTP on Android needs `android:usesCleartextTraffic="true"` in the manifest (dev only).

## Try it

```bash
B=http://localhost:8000/api/v1
curl $B/health
curl $B/categories
curl $B/mock/scan                       # full sample response for Flutter dev
curl -X POST $B/scan \
  -H "X-Device-Id: $(python -c 'import uuid;print(uuid.uuid4())')" \
  -F image=@label.jpg -F food_category=cereals_noodles

# Text only (no image): great for testing the parser and engines
curl -X POST $B/analyze -H "X-Device-Id: $DEVICE" -H 'Content-Type: application/json' -d '{
  "ingredients_text": "Wheat flour (72%), Salt, Emulsifier (322, 471), Colour (INS 102)",
  "nutrition_text": "Energy 1890 kJ, Sugar 3.4 g, Salt 1.5 g",
  "food_category": "bakery"
}'

# History (newest first), one scan, delete
curl "$B/scans?limit=20&offset=0" -H "X-Device-Id: $DEVICE"
curl $B/scans/<scan_id> -H "X-Device-Id: $DEVICE"
curl -X DELETE $B/scans/<scan_id> -H "X-Device-Id: $DEVICE"     # 204, also deletes the photo
```
(`DEVICE=$(python -c 'import uuid;print(uuid.uuid4())')`; in Swagger, fill in the `X-Device-Id` field.)

Run the tests with `pytest` (from this folder).

## How extraction works

1. `sections.py` finds the *Ingredients* / *Nutrition* headings (fuzzy, so `lNGREDlENTS` still works) and cuts the ingredient list at markers like "Allergen", "Manufactured by", "Best before".
2. `ingredient_parser.py` splits on top-level commas (brackets respected), reads percentages and INS/E numbers, expands `Emulsifier (322, 471)` into one item per number, and repairs common OCR slips (`lNS`, `1O2`, `501(l)`, full-width brackets, `.` for `,`).
3. `normalizer.py` maps each item to `rules/additives.json` / `rules/ingredients.json`: INS number, then exact alias, then fuzzy match (rapidfuzz `token_sort_ratio >= 88`). Anything else is `known: false`.
4. `nutrition_parser.py` reads each nutrient with regexes. Energy is returned in kcal (kJ converted), sodium in mg (salt / 2.5 if sodium isn't printed). Missing nutrients stay `null`.

## How the decisions are made

**FSSAI engine** (`engines/fssai_engine.py`, deterministic, no AI). Per ingredient:

| Situation | Result |
|---|---|
| Ingredient not recognised | REVIEW |
| Rule says `NOT_PERMITTED` | FLAG |
| Rule says `PERMITTED` | PASS |
| Rule says `CONDITIONAL` and no food category was sent | REVIEW |
| `CONDITIONAL` and a condition covers the category | that condition's `PASS` / `FLAG` |
| `CONDITIONAL` and no condition covers the category | REVIEW |
| Would be PASS but `match_confidence < MATCH_CONFIDENCE_CUTOFF` (default 0.90, set in `.env`) | REVIEW |

**Declarations** (e.g. "contains permitted colour"): if an ingredient of that category is present and none of the accepted phrases is found in the scanned text, the engine adds **one label-level finding** with `"ingredient_id": null`, status `REVIEW` (never `FLAG`, since OCR may just have missed the text) and reason `"Declaration not found in the scanned area"`. It does not change any ingredient's own finding, and `summary` counts ingredients only (so `pass + flag + review == scanned` always holds).

Overall: any FLAG gives FLAG, otherwise any REVIEW (an ingredient's or a label-level finding) gives REVIEW, otherwise PASS. `confidence = ocr_confidence x matched / scanned` (typed text counts as OCR confidence 1.0). The summary counts each ingredient once, at its worst status.

A `CONDITIONAL` rule looks like `{"food_categories": ["bakery"], "result": "PASS", "note": "..."}` in the entry's `conditions` list (`"*"` matches every category).

**Health engine** (`engines/health_engine.py`). Score starts at `base_score` (100); thresholds and impacts come from `rules/nutrition_rules.json`; only the strictest matching tier per nutrient applies; the result is clamped to 0-100 and mapped to a band (70+ `FEWER CONCERNS`, 40-69 `MODERATE`, below 40 `SEVERAL CONCERNS`).

- **Thresholds** are the UK FSA per-100 g "high" cut-offs: total sugars > 22.5 g, total fat > 17.5 g, saturated fat > 5 g, salt > 1.5 g (= sodium > 600 mg). Beverages (per 100 ml, or food category `beverages_non_alcoholic`) use half. Every threshold has a `source` in the JSON. The trans-fat and energy factors and all the *impact sizes* (points lost) are marked `"project heuristic"`.
- **No usable nutrition** (nothing found, only per-serving values, or no scoring nutrient): coarse ingredient-based rules apply, the assessment is **capped at `MODERATE`** (the score is still computed) and `LIMITED_NUTRITION_DATA` is added to `warnings`.
- **`health_result.data_completeness`** is a string: `"full"` (sugars, total fat, saturated fat and sodium all read), `"partial"` (some nutrients read) or `"ingredients_only"` (no usable nutrition). **`health_result.completeness_score`** is the numeric version: 0.7 x (scoring nutrients present) + 0.3 x (ingredients recognised), from 0 to 1. Show completeness in the app.

Known limits: a comma the OCR drops completely ("Salt Sugar") can't be repaired and gives one unknown ingredient; brackets holding only a descriptor ("Salt (iodised)") are ignored.

## History endpoints (for the Flutter developer)

All three need the `X-Device-Id` header and only ever see that device's scans.

**`GET /api/v1/scans?limit=20&offset=0`** (`limit` 1-100, default 20; `offset` >= 0). Newest first. Returns 200:

```json
{
  "items": [
    {
      "scan_id": "f3d1f1c9-90cc-4324-9d79-9bbf2e1fec64",
      "created_at": "2026-09-25T10:29:39.469425+00:00",
      "food_category": "cereals_noodles",
      "overall_status": "REVIEW",
      "health_score": 57,
      "assessment": "MODERATE",
      "ingredient_count": 7
    }
  ],
  "total": 12,
  "limit": 20,
  "offset": 0
}
```

- `food_category` may be `null`. `overall_status` is `PASS` | `FLAG` | `REVIEW`. `assessment` is `FEWER CONCERNS` | `MODERATE` | `SEVERAL CONCERNS`.
- `total` is the number of scans for this device (use it for paging: fetch the next page while `offset + items.length < total`). An empty history is `{"items": [], "total": 0, ...}`, not an error.

**`GET /api/v1/scans/{scan_id}`** returns 200 with the same full object `/scan` returned. Unknown id or another device's id gives 404 `SCAN_NOT_FOUND`.

**`DELETE /api/v1/scans/{scan_id}`** returns **204 with an empty body** on success (the scan, its stored rows and its photo are deleted). Unknown id or another device's id gives 404 `SCAN_NOT_FOUND`. Deleting twice: the second call is a 404.

## Warnings

`warnings` in the scan response is a list of strings (it can be empty). The app should show a hint for each:

| Warning | Meaning |
|---|---|
| `LOW_OCR_CONFIDENCE` | OCR confidence below 0.75; the text may contain mistakes |
| `NO_NUTRITION_FOUND` | No nutrient values were found on the label |
| `IMPLAUSIBLE_NUTRIENT_IGNORED:<field>` | A value was dropped as an obvious OCR error (e.g. 175 g fat per 100 g) |
| `LIMITED_NUTRITION_DATA` | No usable per-100 g nutrition. The score is computed from ingredients only and the assessment is capped at `MODERATE` |
| `NUTRITION_PER_SERVING_ONLY` | Only a per-serving table was found. It is not compared with the per-100 g thresholds (so `LIMITED_NUTRITION_DATA` is added too) |

## Errors

Always `{"error": {"code": "...", "message": "..."}}`.

| Code | HTTP | Meaning |
|---|---|---|
| `POOR_IMAGE` | 422 | Photo too blurry (Laplacian variance < `BLUR_THRESHOLD`) |
| `NO_TEXT_FOUND` | 422 | No engine could read any text |
| `NO_INGREDIENTS_SECTION` | 422 | Text found but no ingredients section (Phase 2) |
| `INVALID_FILE` | 400 | Not JPG/PNG/WEBP (checked by magic bytes), empty, or missing |
| `FILE_TOO_LARGE` | 413 | Over 5 MB |
| `INVALID_CATEGORY` | 400 | `food_category` is not an id from `/categories` |
| `MISSING_DEVICE_ID` | 400 | The `X-Device-Id` header is missing (required on `/scan`, `/analyze`, `/scans*`) |
| `INVALID_DEVICE_ID` | 400 | `X-Device-Id` is not a UUID |
| `SCAN_NOT_FOUND` | 404 | No scan with that id **for this device** (someone else's scan looks the same) |
| `VALIDATION_ERROR` / `NOT_FOUND` / `INTERNAL_ERROR` | 422 / 404 / 500 | Generic (bad JSON body, unknown URL, server bug) |

## Project layout

```
app/
  main.py          FastAPI app, CORS, global error handlers
  config.py        Settings (.env)
  errors.py        AppError + helpers for the error codes
  schemas.py       Pydantic models = the API contract
  api/routes.py    Endpoints
  pipeline/        preprocessing, ocr, sections, ingredient_parser, nutrition_parser, normalizer
  engines/         fssai_engine.py, health_engine.py
  database.py, models.py   SQLite (scans, ingredients, findings)
  services/        scan_service.py           (orchestration, saving, history)
  rules/           food_categories, additives, ingredients, declarations, nutrition_rules (.json)
tests/             test_parser.py, test_fssai.py, test_health.py, test_history.py
uploads/           saved images (gitignored)
```

## Rule data

Every rule entry carries a `source`. Anything not verified is marked
`"TODO: verify against FSS (FPS&FA) Regulations 2011"`. Verify these before
relying on any result.

- **Until you fill in `conditions`, every additive comes out as REVIEW** (that is deliberate: no rule is verified, so the engine never claims PASS or FLAG for an additive).
- `additives.json`: INS numbers, names and categories come from the Codex INS list, but **every `status` is a `CONDITIONAL` placeholder with empty `conditions`**. Nothing is asserted about what is permitted.
- `ingredients.json`: ordinary foods (`PERMITTED` = "not an additive", itself unverified) and flavour entries (placeholder).
- `declarations.json`: accepted phrases are placeholders.
- `nutrition_rules.json`: the four FSA thresholds are cited; the energy and trans-fat thresholds and every impact size are project heuristics, labelled as such.
