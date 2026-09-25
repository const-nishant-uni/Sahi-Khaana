// ignore_for_file: avoid_print
// Calls every backend endpoint through the app's own API layer and prints PASS/FAIL.
// Needs the backend running. From the sahi_khaana_app folder:
//
//   dart run tool/api_smoke.dart
//   dart run tool/api_smoke.dart --base http://localhost:8000/api/v1 \
//       --image ../sahi-khaana-backend/tests/fixtures/eval/example_1.jpg
//
// (Pure Dart: no Flutter needed, so it also works in CI.)
import 'dart:io';
import 'dart:typed_data';

import 'package:sahi_khaana_app/api/api.dart';
import 'package:sahi_khaana_app/models/models.dart';
import 'package:sahi_khaana_app/services/device_id_store.dart';

var _failures = 0;
var _checks = 0;

void check(String name, bool ok, [String detail = '']) {
  _checks++;
  if (!ok) _failures++;
  print('${ok ? 'PASS' : 'FAIL'} $name${detail.isEmpty ? '' : '  [$detail]'}');
}

/// Runs [body] and expects an [ApiException] with [code].
Future<void> expectError(String name, String code, Future<void> Function() body) async {
  try {
    await body();
    check(name, false, 'no error thrown');
  } on ApiException catch (e) {
    check(name, e.code == code, '${e.code} (HTTP ${e.statusCode})');
  }
}

String arg(List<String> args, String name, String fallback) {
  final i = args.indexOf(name);
  return i >= 0 && i + 1 < args.length ? args[i + 1] : fallback;
}

Future<void> main(List<String> args) async {
  final base = arg(args, '--base', ApiConfig.localBaseUrl);
  final imagePath = arg(args, '--image', '../sahi-khaana-backend/tests/fixtures/eval/example_1.jpg');
  print('Backend: $base\nPhoto:   $imagePath\n');

  final store = InMemoryDeviceIdStore();
  final api = SahiApi(ApiClient(config: ApiConfig(baseUrl: base), deviceIdStore: store));
  final otherApi = SahiApi(ApiClient(config: ApiConfig(baseUrl: base), deviceIdStore: InMemoryDeviceIdStore()));

  try {
    // ---- no-login basics
    check('health', (await api.health()).isNotEmpty);
    final categories = await api.categories();
    check('categories', categories.length >= 10, '${categories.length} categories, first "${categories.first.name}"');
    final mock = await api.mockScan();
    check('mockScan', mock.ingredients.any((i) => i.repaired) && mock.fssaiResult.labelLevelFindings.isNotEmpty);

    // ---- scan a real photo
    final scan = await api.scanFile(imagePath, foodCategory: 'cereals_noodles');
    check('scanFile', scan.ocr != null && scan.ocr!.confidence > 0.8, 'OCR ${scan.ocr?.engine} ${scan.ocr?.confidence}');
    check('  ingredients', scan.ingredients.length >= 7, '${scan.ingredients.length}: ${scan.ingredients.take(4).map((i) => i.displayName).join(', ')}...');
    check('  nutrition read', scan.nutrition.sodiumMg == 1240 && scan.nutrition.basis == NutritionBasis.per100g);
    final s = scan.fssaiResult.summary;
    check('  fssai summary adds up', s.pass + s.flag + s.review == s.scanned, '${scan.fssaiResult.overallStatus.apiValue} $s'.replaceAll('Instance of \'FssaiSummary\'', 'pass=${s.pass} flag=${s.flag} review=${s.review}'));
    check('  label-level finding present', scan.fssaiResult.labelLevelFindings.isNotEmpty);
    check('  health', scan.healthResult.score >= 0 && scan.healthResult.dataCompleteness == DataCompleteness.full, '${scan.healthResult.score} ${scan.healthResult.assessment.apiValue}');

    // ---- analyze
    final repaired = await api.analyze(AnalyzeRequest(
      ingredientsText: 'Refinedwheatflour (72%), Sugar, Salt',
      nutritionText: 'per 100 g: Total sugars 12 g, Sodium 300 mg',
      foodCategory: 'bakery',
    ));
    check('analyze: repaired ingredient', repaired.ocr == null && repaired.ingredients.first.repaired && repaired.ingredients.first.original == 'Refinedwheatflour (72%)' && repaired.ingredients.first.normalized == 'wheat flour');
    final limited = await api.analyze(AnalyzeRequest(ingredientsText: 'Sugar, Colour (INS 102), Preservative (INS 211)'));
    check('analyze: limited nutrition warning + capped', limited.hasWarning(ScanWarnings.limitedNutritionData) && limited.healthResult.assessment != HealthAssessment.fewerConcerns && limited.healthResult.dataCompleteness == DataCompleteness.ingredientsOnly);
    final perServing = await api.analyze(AnalyzeRequest(ingredientsText: 'Sugar, Salt', nutritionText: 'per serving: Energy 100 kcal'));
    check('analyze: per-serving warning', perServing.hasWarning(ScanWarnings.nutritionPerServingOnly));

    // ---- history
    final page = await api.listScans();
    check('listScans (4 scans, newest first)', page.total == 4 && page.items.first.scanId == perServing.scanId && page.items.last.scanId == scan.scanId, 'total ${page.total}, hasMore ${page.hasMore}');
    final page2 = await api.listScans(limit: 2, offset: 1);
    check('listScans paging', page2.items.length == 2 && page2.hasMore && page2.nextOffset == 3 && page2.items.first.scanId == limited.scanId);
    final again = await api.getScan(scan.scanId);
    check('getScan matches the scan', again.scanId == scan.scanId && again.healthResult.score == scan.healthResult.score && again.ingredients.length == scan.ingredients.length && again.ocr?.rawText == scan.ocr?.rawText);

    // ---- explanation
    final e1 = await api.explanation(scan.scanId);
    final e2 = await api.explanation(scan.scanId);
    check('explanation', e1.text.isNotEmpty && e1.text == e2.text && e1.source == e2.source, 'source ${e1.source.apiValue}, ${e1.text.split(' ').length} words');
    print('    "${e1.text}"');

    // ---- errors + isolation
    await expectError('bad category', ApiErrorCodes.invalidCategory, () => api.analyze(AnalyzeRequest(ingredientsText: 'Sugar', foodCategory: 'nope')));
    await expectError('not an image', ApiErrorCodes.invalidFile, () async => api.scanBytes(Uint8List.fromList('hello'.codeUnits), filename: 'x.jpg'));
    await expectError('unknown scan', ApiErrorCodes.scanNotFound, () => api.getScan('does-not-exist'));
    await expectError("other device can't read my scan", ApiErrorCodes.scanNotFound, () => otherApi.getScan(scan.scanId));
    await expectError("other device can't delete it", ApiErrorCodes.scanNotFound, () => otherApi.deleteScan(scan.scanId));
    await expectError("other device can't get the explanation", ApiErrorCodes.scanNotFound, () => otherApi.explanation(scan.scanId));
    check("other device's history is empty", (await otherApi.listScans()).total == 0);
    final blank = File('${Directory.systemTemp.path}/sahi_smoke_blank.jpg');
    await expectError('featureless photo is rejected', ApiErrorCodes.poorImage, () async {
      // A flat grey JPEG: valid file, nothing to read.
      blank.writeAsBytesSync(_flatGreyJpeg);
      await api.scanFile(blank.path);
    });
    if (blank.existsSync()) blank.deleteSync();

    // ---- delete
    await api.deleteScan(scan.scanId);
    check('deleteScan then getScan -> 404', await _throws(ApiErrorCodes.scanNotFound, () => api.getScan(scan.scanId)));
    check('deleteScan twice -> 404', await _throws(ApiErrorCodes.scanNotFound, () => api.deleteScan(scan.scanId)));
    check('history now has 3', (await api.listScans()).total == 3);
  } on ApiException catch (e) {
    check('unexpected ApiException', false, e.toString());
  } finally {
    api.close();
    otherApi.close();
  }

  print('\n${_checks - _failures}/$_checks checks passed');
  exit(_failures == 0 ? 0 : 1);
}

Future<bool> _throws(String code, Future<Object?> Function() body) async {
  try {
    await body();
    return false;
  } on ApiException catch (e) {
    return e.code == code;
  }
}

// A valid 16x16 flat grey JPEG (to trigger POOR_IMAGE).
final _flatGreyJpeg = Uint8List.fromList(const [
  0xff, 0xd8, 0xff, 0xe0, 0x00, 0x10, 0x4a, 0x46, 0x49, 0x46, 0x00, 0x01, 0x01, 0x00, 0x00, 0x01, 0x00, 0x01, 0x00, 0x00,
  0xff, 0xdb, 0x00, 0x43, 0x00, 0x08, 0x06, 0x06, 0x07, 0x06, 0x05, 0x08, 0x07, 0x07, 0x07, 0x09, 0x09, 0x08, 0x0a, 0x0c,
  0x14, 0x0d, 0x0c, 0x0b, 0x0b, 0x0c, 0x19, 0x12, 0x13, 0x0f, 0x14, 0x1d, 0x1a, 0x1f, 0x1e, 0x1d, 0x1a, 0x1c, 0x1c, 0x20,
  0x24, 0x2e, 0x27, 0x20, 0x22, 0x2c, 0x23, 0x1c, 0x1c, 0x28, 0x37, 0x29, 0x2c, 0x30, 0x31, 0x34, 0x34, 0x34, 0x1f, 0x27,
  0x39, 0x3d, 0x38, 0x32, 0x3c, 0x2e, 0x33, 0x34, 0x32, 0xff, 0xc0, 0x00, 0x0b, 0x08, 0x00, 0x10, 0x00, 0x10, 0x01, 0x01,
  0x11, 0x00, 0xff, 0xc4, 0x00, 0x14, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
  0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0xff, 0xc4, 0x00, 0x14, 0x10, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
  0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0xff, 0xda, 0x00, 0x08, 0x01, 0x01, 0x00, 0x00, 0x3f, 0x00,
  0x7f, 0xff, 0xd9,
]);
