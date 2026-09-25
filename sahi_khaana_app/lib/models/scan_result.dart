import 'fssai_result.dart';
import 'health_result.dart';
import 'ingredient.dart';
import 'json_helpers.dart';
import 'nutrition.dart';
import 'warnings.dart';

/// `ocr`: what the text reader saw. Null for typed text (`/analyze`).
class OcrInfo {
  const OcrInfo({
    required this.rawText,
    required this.confidence,
    required this.engine,
  });

  factory OcrInfo.fromJson(Json json) => OcrInfo(
    rawText: json['raw_text'] as String,
    confidence: asDouble(json['confidence']),
    engine: json['engine'] as String,
  );

  final String rawText;

  /// 0..1.
  final double confidence;

  /// "rapidocr", "rapidocr-original" or "tesseract".
  final String engine;
}

/// The full result returned by `POST /scan`, `POST /analyze` and `GET /scans/{id}`.
class ScanResult {
  const ScanResult({
    required this.scanId,
    required this.createdAt,
    required this.status,
    required this.warnings,
    required this.ocr,
    required this.foodCategory,
    required this.ingredients,
    required this.nutrition,
    required this.fssaiResult,
    required this.healthResult,
  });

  factory ScanResult.fromJson(Json json) => ScanResult(
    scanId: json['scan_id'] as String,
    createdAt: DateTime.parse(json['created_at'] as String),
    status: json['status'] as String? ?? 'ok',
    warnings: asStringList(json['warnings']),
    ocr: json['ocr'] == null ? null : OcrInfo.fromJson(json['ocr'] as Json),
    foodCategory: json['food_category'] as String?,
    ingredients: asObjectList(json['ingredients'], Ingredient.fromJson),
    nutrition: Nutrition.fromJson(json['nutrition'] as Json),
    fssaiResult: FssaiResult.fromJson(json['fssai_result'] as Json),
    healthResult: HealthResult.fromJson(json['health_result'] as Json),
  );

  final String scanId;

  /// UTC.
  final DateTime createdAt;

  /// Always "ok".
  final String status;

  /// Raw warning strings; see [ScanWarnings] and [hasWarning].
  final List<String> warnings;

  /// Null when the result came from typed text.
  final OcrInfo? ocr;

  /// The category id that was sent, if any.
  final String? foodCategory;
  final List<Ingredient> ingredients;
  final Nutrition nutrition;
  final FssaiResult fssaiResult;
  final HealthResult healthResult;

  /// True if [code] (a [ScanWarnings] constant) is present, ignoring any ':' suffix.
  bool hasWarning(String code) =>
      warnings.any((w) => ScanWarnings.codeOf(w) == code);

  /// Field names from `IMPLAUSIBLE_NUTRIENT_IGNORED:<field>` warnings.
  List<String> get ignoredNutrientFields => [
    for (final w in warnings)
      if (ScanWarnings.codeOf(w) == ScanWarnings.implausibleNutrientIgnored &&
          w.contains(':'))
        w.substring(w.indexOf(':') + 1),
  ];
}
