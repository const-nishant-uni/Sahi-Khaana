# CI/CD

GitHub Actions, in `.github/workflows/`. Backend and app have their own pipelines and their own release tags.

## What runs when

| Workflow | Runs on | What it does |
|---|---|---|
| **Backend CI** (`backend-ci.yml`) | push to `master` / any PR touching `sahi-khaana-backend/` | `pytest` on Python 3.11 with Tesseract installed; then builds the Docker image, starts it, and calls the API inside it (health, categories, a real photo scan through OCR, history, Tesseract present, and **an explanation that must come from the LLM when a Groq key is set**) |
| **App CI** (`app-ci.yml`) | push to `master` / any PR touching `sahi_khaana_app/` | `flutter analyze`, `flutter test`, then a debug APK build (uploaded as an artifact for 7 days) |
| **API contract** (`api-contract.yml`) | push to `master` / any PR touching **either** folder | starts the real backend and runs `tool/api_smoke.dart`, which drives every endpoint through the app's own Dart API layer (27 checks, 28 with a Groq key, which adds "the explanation came from the LLM"). Fails if the app's models and the backend's responses drift apart |
| **Backend release** (`backend-release.yml`) | tag `vX.Y.Z-backend` | re-runs Backend CI, pushes the Docker image to GitHub Container Registry, creates a GitHub Release |
| **App release** (`app-release.yml`) | tag `vX.Y.Z-app` | re-runs App CI, builds a release APK, attaches it (plus a `.sha256`) to a GitHub Release |

All CI workflows can also be started by hand (Actions tab, "Run workflow"). Runs for the same branch cancel each other, so only the latest push is tested.

## Making a release

Backend (image `ghcr.io/<owner>/sahi-khaana-backend:<version>` and `:latest`):

```bash
git tag -a v1.2.0-backend -m "Backend 1.2.0"
git push origin v1.2.0-backend
```

App (APK on the GitHub Release). First set `version:` in `sahi_khaana_app/pubspec.yaml` to the same number
(`version: 1.2.0+3`, where `+3` is the build number). The workflow **fails on purpose** if the tag and pubspec disagree.

```bash
git tag -a v1.2.0-app -m "App 1.2.0"
git push origin v1.2.0-app
```

A malformed tag (`v1-backend`, `vfoo-app`) is rejected before anything is published. Tags that already existed before
these workflows (`v1.0-backend`, `v1.0.1-backend`) did not trigger anything and will not run retroactively.

## One-time setup on GitHub

1. **Actions must be enabled** for the repository (Settings > Actions). The workflows declare their own permissions,
   so nothing needs changing under "Workflow permissions".
2. **Secret `GROQ_API_KEY`** (Settings > Secrets and variables > Actions > *Secrets* > New repository secret).
   Optional variable **`GROQ_MODEL`** (same page, *Variables*) to override the backend's default model. Set it only if
   you want a different one; leaving it unset uses the default in `config.py`.
3. **Optional variable `API_BASE_URL`** (Settings > Secrets and variables > Actions > *Variables*): the backend address
   baked into the release APK, e.g. `https://api.example.com/api/v1`. If unset, the APK uses the app's built-in
   development address (`http://10.0.2.2:8000/api/v1`, which only works on an Android emulator).
4. **Pulling the image** from a private repo needs a personal access token with `read:packages`
   (`docker login ghcr.io -u <user>`). Package visibility can be changed on the package's page.
5. If you enable **branch protection with required checks**, be aware the workflows are path-filtered: a PR that only
   touches one folder never starts the other pipeline, and a required check that never runs stays "pending".
   Require only the checks that always apply, or drop the path filters.

## Secrets and the Groq key

`GROQ_API_KEY` is used in exactly two places, and only to worded explanations (it never affects a status):

| Where | How it gets the key | What it checks |
|---|---|---|
| **API contract**, "Start the backend" step | env of that one step, so only the server process sees it | with the key, `tool/api_smoke.dart --expect-llm` fails unless the explanation `source` is `"llm"` |
| **Backend CI**, "Start the container" step | `docker run -e GROQ_API_KEY` (by name, so it never appears on a command line) | same check against the container |

- **It is a canary.** A retired or misspelt model makes Groq answer 404, and the backend then quietly falls back to the
  template. With a key set, CI fails loudly instead (this exact thing happened when the Llama models were retired). If it
  fails after a green period, run `curl -s https://api.groq.com/openai/v1/models -H "Authorization: Bearer $GROQ_API_KEY"`,
  pick a current chat model, and set the `GROQ_MODEL` variable (or change the default in `config.py`).
- **Not used by `pytest`.** The tests strip the key and block real network calls, so they never spend it.
- **Never baked into anything.** Not in the Docker image, not in the APK, not in logs (GitHub also masks it).
- **No key, still green.** If the secret is missing, or the run has no access to secrets (pull requests from forks,
  Dependabot), both checks fall back to the template path and pass.
- **Releases** re-run the Docker check with the key (`secrets: inherit`) before publishing the image.
- Cost: two small API calls per CI run.
- Rotating the key: update the repository secret; nothing else changes. Give the *deployed* container its key at
  runtime instead: `docker run --env-file .env ...`.

## Running the same checks locally

```bash
# backend
cd sahi-khaana-backend && python -m pytest -q
docker build -t sahi-khaana-backend . && docker run -p 8000:8000 --env-file .env -v sahi-data:/data sahi-khaana-backend

# app
cd sahi_khaana_app && flutter analyze && flutter test && flutter build apk --debug

# contract (backend running on :8000)
cd sahi_khaana_app && dart run tool/api_smoke.dart --base http://localhost:8000/api/v1
```

## Known limits (read before relying on it)

- **Nothing is deployed to a server.** The release publishes an image and an APK; running the image somewhere
  (a VM, Fly.io, Render, Cloud Run...) is not automated because no target has been chosen. Adding it later means one more
  job in `backend-release.yml` with the host's credentials stored as repository secrets.
- **The release APK is signed with the Flutter debug key** (the project has no release keystore), so it is for testing
  on devices, not for the Play Store. It also still allows plain-HTTP traffic (`usesCleartextTraffic`, see the manifest).
  Add a keystore (as secrets) and switch to HTTPS before any public release.
- **The Docker image had never been built before these workflows** (no Docker daemon was available while writing it).
  The first Backend CI run is its first real test; if it fails, read the "Build the image" or "Wait for the server" step.
- **Cost:** the app's Android build and the Docker builds are the slow jobs (several minutes each). On a private
  repository they use the free monthly Actions minutes.
