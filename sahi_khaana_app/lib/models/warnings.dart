/// Codes that can appear in `ScanResult.warnings`.
///
/// A warning may carry a suffix after a colon (`IMPLAUSIBLE_NUTRIENT_IGNORED:total_fat_g`);
/// compare with [ScanWarnings.codeOf], not with `==` on the whole string.
abstract final class ScanWarnings {
  /// OCR confidence below 0.75: the text may contain mistakes.
  static const lowOcrConfidence = 'LOW_OCR_CONFIDENCE';

  /// No nutrient values were found on the label.
  static const noNutritionFound = 'NO_NUTRITION_FOUND';

  /// A value was dropped as an obvious OCR error. Suffix = the field name.
  static const implausibleNutrientIgnored = 'IMPLAUSIBLE_NUTRIENT_IGNORED';

  /// No usable per-100 g nutrition: the score uses ingredients only and the
  /// assessment is capped at MODERATE.
  static const limitedNutritionData = 'LIMITED_NUTRITION_DATA';

  /// Only a per-serving table was found; it is not scored.
  static const nutritionPerServingOnly = 'NUTRITION_PER_SERVING_ONLY';

  /// The part of [warning] before any ':' suffix.
  static String codeOf(String warning) => warning.split(':').first;
}
