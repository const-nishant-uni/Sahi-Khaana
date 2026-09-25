# Sahi Khaana app

Flutter client for the Sahi Khaana backend (photo of a food label in, FSSAI rule check and
health view out). **Status: the API layer is done; the UI is not started** (`lib/main.dart` is still
the Flutter counter demo).

The backend contract is documented in
[`../sahi-khaana-backend/docs/API_CHANGES.md`](../sahi-khaana-backend/docs/API_CHANGES.md).
This app's `lib/api` and `lib/models` follow it field for field.

## What is here

```
lib/
  api/
    api.dart                barrel: import this
    api_config.dart         base URL (per platform / --dart-define) and timeouts
    api_client.dart         HTTP: X-Device-Id header, timeouts, UTF-8, error mapping
    api_exception.dart      ApiException + ApiErrorCodes (every backend + client error code)
    sahi_api.dart           one typed method per endpoint
  models/                   ScanResult, Ingredient, Nutrition, FssaiResult, Finding, HealthResult,
                            ScanPage, Explanation, FoodCategory, AnalyzeRequest, enums, warnings
  services/
    device_id_store.dart              the anonymous device UUID (interface + in-memory)
    shared_prefs_device_id_store.dart persisted with shared_preferences
    api_provider.dart                 createSahiApi(): the ready-to-use instance for the app
tool/api_smoke.dart         calls every endpoint against a running backend
test/                       94 tests (models, client, endpoints, device id, config)
```

The API layer and models import **no Flutter code**, so they are plain Dart and easy to test.

## Run it

1. Start the backend (see its README): `uvicorn app.main:app --host 0.0.0.0`.
2. Point the app at it:

| Where the app runs | Base URL | How |
|---|---|---|
| Android emulator | `http://10.0.2.2:8000/api/v1` | default, nothing to do |
| Physical phone, same Wi-Fi | `http://<your PC's LAN IP>:8000/api/v1` | `flutter run --dart-define=API_BASE_URL=http://192.168.1.20:8000/api/v1` |
| Physical phone over USB | `http://localhost:8000/api/v1` | `adb reverse tcp:8000 tcp:8000`, then `--dart-define=API_BASE_URL=http://localhost:8000/api/v1` |
| Desktop / iOS simulator | `http://localhost:8000/api/v1` | default |

`AndroidManifest.xml` declares `INTERNET` and `usesCleartextTraffic="true"` (the dev backend is plain HTTP).
**Remove the cleartext flag and use HTTPS before publishing.**

## Using it from the UI

Create the API **once** at startup and share it (Provider, get_it, a global, whatever you pick):

```dart
import 'package:sahi_khaana_app/api/api.dart';
import 'package:sahi_khaana_app/models/models.dart';
import 'package:sahi_khaana_app/services/api_provider.dart';

final api = createSahiApi();

// Dropdown
final List<FoodCategory> categories = await api.categories();

// Photo (image_picker)
final xfile = await ImagePicker().pickImage(source: ImageSource.camera);
if (xfile != null) {
  final ScanResult result = await api.scanBytes(
    await xfile.readAsBytes(),
    filename: xfile.name,
    foodCategory: selectedCategory?.id,
  );
}

// Typed text instead of a photo
final result = await api.analyze(AnalyzeRequest(ingredientsText: 'Wheat flour (72%), Salt'));

// History, one scan, explanation, delete
final ScanPage page = await api.listScans(limit: 20, offset: 0); // page.hasMore, page.nextOffset
final ScanResult scan = await api.getScan(id);
final Explanation e = await api.explanation(id); // first call can take a few seconds
await api.deleteScan(id);
```

### Errors

Every failure is an `ApiException`; switch on `code`, never on the message:

```dart
try {
  await api.scanBytes(...);
} on ApiException catch (e) {
  if (e.isRetakePhoto) { /* POOR_IMAGE, NO_TEXT_FOUND, NO_INGREDIENTS_SECTION */ }
  else if (e.code == ApiErrorCodes.fileTooLarge) { ... }
  else if (e.isNetworkProblem) { /* NETWORK_ERROR or TIMEOUT: server unreachable */ }
}
```

`ApiErrorCodes` lists every code (the backend's plus the client-side `NETWORK_ERROR`, `TIMEOUT`,
`BAD_RESPONSE`).

### Reading a result

- `result.fssaiResult.overallStatus` is `pass`, `flag` or `review`. Unknown values from a newer backend
  become `review` (the safe choice).
- `fssaiResult.labelLevelFindings` are findings about the whole label (their `ingredientId` is null);
  `findingsFor(ingredient.id)` gives one ingredient's findings.
- `result.healthResult.dataCompleteness` is an enum (`full`, `partial`, `ingredientsOnly`);
  the number is `completenessScore`.
- `result.hasWarning(ScanWarnings.limitedNutritionData)` ignores any `:suffix`.
- `ingredient.original` is the raw OCR token; `ingredient.repaired` says the backend split run-together
  words to match it; `ingredient.displayName` is the matched name when there is one.
- Until the backend's rule data is verified, expect `review` for almost every additive.

## Device id

The backend has no login. `X-Device-Id` (a UUID) is the only key to a user's history. It is created on first
use, stored with `shared_preferences`, and sent on every request automatically. Reinstalling the app
creates a new id, so the old history becomes unreachable.

## Tests and the live check

```bash
flutter analyze
flutter test                        # 94 tests, no server needed (HTTP is faked)

# Against a running backend (calls every endpoint, expects 27 checks to pass):
dart run tool/api_smoke.dart --base http://localhost:8000/api/v1
```

`test/fixtures/*.json` are real backend responses.

## Not done yet

The UI: screens, navigation, state management, camera/gallery flow, the theme. `main.dart` and
`test/widget_test.dart` are still the Flutter template.
