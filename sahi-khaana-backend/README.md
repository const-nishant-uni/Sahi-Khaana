# Sahi Khaana - Backend

FastAPI backend for the Sahi Khaana Flutter app. A user photographs a packaged
food's ingredient label; the backend preprocesses the image (OpenCV), reads it
(OCR), extracts ingredients and nutrition, applies **deterministic** FSSAI rules
(PASS / FLAG / REVIEW) and a configurable health assessment, and returns JSON.

> Principle: OCR/AI extracts information; deterministic rules make the
> regulatory decision. An LLM only phrases explanations, never decides.

**Flutter developer: start with [docs/API_CHANGES.md](docs/API_CHANGES.md)** (checklist of changes, every endpoint, field, warning and error code, with real example responses).

## Status: Phase 4 (explanation + polish), backend frozen at `v1.0-backend`

| Part | State |
|---|---|
| Upload validation, preprocessing, OCR (RapidOCR + Tesseract fallback) | real |
| Section finding, `ingredients`, `nutrition`, `POST /analyze` | real |
| FSSAI rule engine, health engine | real (but the **rule data is placeholder**, see "Rule data") |
| SQLite history: `GET /scans`, `GET /scans/{id}`, `DELETE /scans/{id}` | real |
| `GET /scans/{id}/explanation` (Groq LLM with template fallback), 7-day photo cleanup | real |
| `scripts/evaluate.py`, optional `Dockerfile` | real (the Dockerfile is untested, see below) |

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
- **Schema changed - delete your local .db file after pulling.** (`sahi_khaana.db` in this folder; it is recreated on the next start. Existing tables are not migrated.)
- The SQLite file `sahi_khaana.db` is created on first start (gitignored).
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

0. `preprocessing.py` resizes, checks blur, then cleans the image (CLAHE, denoise, deskew). If the estimated median text-line height is under `MIN_TEXT_HEIGHT_PX` (default 30; `0` turns it off), both images are also **upscaled 2x** before OCR, because RapidOCR drops word spaces on small text. On rendered test labels this cut the word error rate by 60-80% for text lines of roughly 22-27 px and changed nothing above 30 px; on very tiny text (under about 18 px) the result was mixed. It costs about 20 ms plus a few hundred ms of extra OCR time.
1. `sections.py` finds the *Ingredients* / *Nutrition* headings (fuzzy, so `lNGREDlENTS` still works) and cuts the ingredient list at markers like "Allergen", "Manufactured by", "Best before".
2. `ingredient_parser.py` splits on top-level commas (brackets respected), reads percentages and INS/E numbers, expands `Emulsifier (322, 471)` into one item per number, and repairs common OCR slips (`lNS`, `1O2`, `501(l)`, full-width brackets, `.` for `,`).
3. `normalizer.py` maps each item to `rules/additives.json` / `rules/ingredients.json`: INS number, then exact alias, then fuzzy match (rapidfuzz `token_sort_ratio >= 88`). If all of that fails and the token is a single word of 12+ letters, it is split into known words by dictionary segmentation (`Refinedwheatflour` becomes `Refined Wheat Flour`) and matched again; the split is kept only if that match passes the same cutoff. Such an ingredient keeps the raw OCR token in `original` (`Refinedwheatflour`), holds the matched name in `normalized`, and has **`repaired: true`** (it is `false` for every ordinary match). Anything else is `known: false`.
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

- **Thresholds** are the UK FSA per-100 g cut-offs. *High* (big penalty): total sugars > 22.5 g, total fat > 17.5 g, saturated fat > 5 g, salt > 1.5 g (= sodium > 600 mg). *Medium* (above the FSA "low" cut-off, **-5 points**): sugars > 5 g, total fat > 3 g, saturated fat > 1.5 g, sodium > 120 mg (= salt > 0.3 g). Only the strictest matching tier applies, so nothing is double counted. Beverages (per 100 ml, or food category `beverages_non_alcoholic`) use half of every one of these. Every threshold has a `source` in the JSON. The trans-fat and energy factors and all the *impact sizes* (points lost) are marked `"project heuristic"`.
- **No usable nutrition** (nothing found, only per-serving values, or no scoring nutrient): coarse ingredient-based rules apply, the assessment is **capped at `MODERATE`** (the score is still computed) and `LIMITED_NUTRITION_DATA` is added to `warnings`.
- **`health_result.data_completeness`** is a string: `"full"` (sugars, total fat, saturated fat and sodium all read), `"partial"` (some nutrients read) or `"ingredients_only"` (no usable nutrition). **`health_result.completeness_score`** is the numeric version: 0.7 x (scoring nutrients present) + 0.3 x (ingredients recognised), from 0 to 1. Show completeness in the app.

Known limits: a comma the OCR drops completely ("Salt Sugar") can't be repaired and gives one unknown ingredient; run-together words are only repaired for single tokens of 12+ letters made of words that appear in the rule data; brackets holding only a descriptor ("Salt (iodised)") are ignored.

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

**`GET /api/v1/scans/{scan_id}/explanation`** returns 200 `{"explanation": "...", "source": "llm" | "template"}` (same 404 rules as above).

- Generated on the first request. **Cached in the database** when it is final: an `"llm"` answer, or the template when no `GROQ_API_KEY` is configured (nothing to retry). If the LLM call fails (timeout, error, empty answer, over 120 words) you get the template but it is **not cached**, so the next request tries the LLM again. A cached LLM answer is never replaced.
- `"llm"`: worded by Groq. It is given only `fssai_result`, `health_result` and `warnings`, is told never to change a status, to stay under 120 words, and to make no medical or compliance claims. `"template"`: built directly from the finding reasons and factor labels (no API key, timeout after 10 s, HTTP error, empty answer, or an answer over 120 words).
- The explanation never affects any status or score. It can take a few seconds the first time.
- Set `GROQ_API_KEY` (and optionally `GROQ_MODEL`, default `qwen/qwen3.8-27b`) in `.env`. Without a key you always get the template.
- **If explanations always say `"template"` even with a key**, the model id is probably unavailable: Groq retires models (`llama-3.1-8b-instant` and `llama-3.3-70b-versatile` now return 404 `model_not_found`), and the server log then shows `Groq explanation failed (HTTPStatusError)`. List the models your key can use with `curl -s https://api.groq.com/openai/v1/models -H "Authorization: Bearer $GROQ_API_KEY"` and set `GROQ_MODEL` in `.env`. **A `GROQ_MODEL` line in `.env` overrides the default**, so an old value there must be updated by hand. Avoid `openai/gpt-oss-*`: they spend the 250-token limit on hidden reasoning and return empty text, so you would always get the template.

## Photo cleanup

On startup, stored photos older than 7 days (`IMAGE_RETENTION_DAYS`) are deleted from `uploads/` and `scans.image_name` is set to `NULL`. The scan results stay in history; only the photo goes. Orphan files (e.g. photos of scans that failed with `POOR_IMAGE`) are removed the same way.

## Evaluating accuracy

`scripts/evaluate.py` runs the pipeline on labelled photos and reports OCR and rule accuracy.

```bash
python scripts/evaluate.py                       # uses tests/fixtures/eval, writes eval_report.md
python scripts/evaluate.py --dir my_fixtures --out my_report.md
```

Put pairs of files in `tests/fixtures/eval/`: `<name>.jpg` (or `.png`/`.webp`) and `<name>.json`:

```json
{
  "ground_truth_text": "INGREDIENTS: Wheat flour (72%), Salt, Preservative (INS 211).\nNUTRITION INFORMATION per 100 g: Sodium 900 mg",
  "expected_ingredients": ["wheat flour", "salt", "sodium benzoate"],
  "expected_statuses": {"wheat flour": "PASS", "sodium benzoate": "REVIEW", "overall": "REVIEW"},
  "food_category": "bakery"
}
```

| Field | Meaning |
|---|---|
| `ground_truth_text` | The label text exactly as printed. Used for CER/WER (compared case-insensitively, whitespace collapsed). |
| `expected_ingredients` | Ingredient names as the normalizer should output them (`normalized`, or the printed text for unknown ones). Used for precision/recall. |
| `expected_statuses` | `PASS`/`FLAG`/`REVIEW` per ingredient name, plus the optional key `"overall"`. Status agreement = entries matched / entries given. |
| `food_category` | A category id from `GET /categories`, or `null`. |

Report: CER and WER (jiwer), ingredient precision and recall (micro-averaged over all fixtures), status agreement %, and the mean time per stage (preprocess, OCR, extraction, engines), as a markdown table on stdout and in `eval_report.md` (gitignored). A fixture whose scan fails (e.g. `POOR_IMAGE`) counts as zero ingredients and zero statuses matched. JSON files without a photo are skipped and listed.

The two shipped examples (`example_1`, `example_2`) use **synthetic photos** (text rendered onto an image), so their scores say nothing about real packs; add real photos and verified `expected_statuses`. The example statuses match the *placeholder* rule data (every additive is REVIEW) and will need updating once you fill in `conditions`.

## Docker (optional)

```bash
docker build -t sahi-khaana-backend .
docker run -p 8000:8000 --env-file .env -v sahi-data:/data sahi-khaana-backend
```

`python:3.11-slim` plus `tesseract-ocr`; the database and photos live in the `/data` volume. **This Dockerfile has not been built or run yet** (no Docker daemon was available when it was written), so treat the first build as a test.

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
  services/        scan_service.py           (orchestration, saving, history, cleanup)
                   explanation.py            (Groq wording + template fallback)
  rules/           food_categories, additives, ingredients, declarations, nutrition_rules (.json)
tests/             test_parser, test_fssai, test_health, test_history, test_explanation, test_cleanup, test_evaluate
  fixtures/eval/   example evaluation fixtures
scripts/evaluate.py  accuracy report
Dockerfile         optional
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
