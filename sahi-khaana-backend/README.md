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
| Would be PASS but `match_confidence < 0.95` | REVIEW |
| Declaration rule (e.g. "contains permitted colour") and the phrase is missing from the label text | REVIEW |

Overall: any FLAG gives FLAG, otherwise any REVIEW gives REVIEW, otherwise PASS. `confidence = ocr_confidence x matched / scanned` (typed text counts as OCR confidence 1.0). The summary counts each ingredient once, at its worst status.

A `CONDITIONAL` rule looks like `{"food_categories": ["bakery"], "result": "PASS", "note": "..."}` in the entry's `conditions` list (`"*"` matches every category).

**Health engine** (`engines/health_engine.py`). Score starts at `base_score` (100); thresholds and impacts come from `rules/nutrition_rules.json`; only the strictest matching tier per nutrient applies; the result is clamped to 0-100 and mapped to a band. Values are per 100 g, so a per-serving table is not scored. With no usable nutrition, coarse ingredient-based rules apply instead. `data_completeness` = 0.7 x (scoring nutrients present) + 0.3 x (ingredients recognised); **show it in the app**, because a product with no nutrition table can score high simply because nothing is known.

Known limits: a comma the OCR drops completely ("Salt Sugar") can't be repaired and gives one unknown ingredient; brackets holding only a descriptor ("Salt (iodised)") are ignored.

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
| `INVALID_DEVICE_ID` | 400 | `X-Device-Id` is not a UUID |
| `VALIDATION_ERROR` / `NOT_FOUND` / `INTERNAL_ERROR` | 422 / 404 / 500 | Generic |

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
- `declarations.json`: accepted phrases are placeholders. `nutrition_rules.json`: health thresholds are placeholder heuristics, not regulatory limits.
