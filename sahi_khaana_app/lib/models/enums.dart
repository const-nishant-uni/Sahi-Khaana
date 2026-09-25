/// Enums for the string values the backend sends.
///
/// Each `fromApi` falls back to the SAFE value for an unknown string, so a backend that
/// later adds a value never crashes the app: unknown status -> review, unknown assessment
/// -> moderate, and so on.
library;

/// `fssai_result.overall_status`, `findings[].status`, `GET /scans` `overall_status`.
enum FssaiStatus {
  pass('PASS'),
  flag('FLAG'),
  review('REVIEW');

  const FssaiStatus(this.apiValue);
  final String apiValue;

  static FssaiStatus fromApi(String? value) =>
      values.firstWhere((s) => s.apiValue == value, orElse: () => review);
}

/// `health_result.assessment`.
enum HealthAssessment {
  fewerConcerns('FEWER CONCERNS'),
  moderate('MODERATE'),
  severalConcerns('SEVERAL CONCERNS');

  const HealthAssessment(this.apiValue);
  final String apiValue;

  static HealthAssessment fromApi(String? value) =>
      values.firstWhere((a) => a.apiValue == value, orElse: () => moderate);
}

/// `health_result.data_completeness` (a string since the backend's Phase 3 fixes).
enum DataCompleteness {
  full('full'),
  partial('partial'),
  ingredientsOnly('ingredients_only');

  const DataCompleteness(this.apiValue);
  final String apiValue;

  static DataCompleteness fromApi(String? value) => values.firstWhere(
    (c) => c.apiValue == value,
    orElse: () => ingredientsOnly,
  );
}

/// `health_result.factors[].type`.
enum HealthFactorType {
  nutrient('nutrient'),
  ingredient('ingredient');

  const HealthFactorType(this.apiValue);
  final String apiValue;

  static HealthFactorType fromApi(String? value) =>
      values.firstWhere((t) => t.apiValue == value, orElse: () => nutrient);
}

/// `nutrition.basis`. `null` in the model means "not stated".
enum NutritionBasis {
  per100g('per_100g'),
  per100ml('per_100ml'),
  perServing('per_serving');

  const NutritionBasis(this.apiValue);
  final String apiValue;

  static NutritionBasis? fromApi(String? value) {
    for (final b in values) {
      if (b.apiValue == value) return b;
    }
    return null;
  }
}

/// `GET /scans/{id}/explanation` `source`.
enum ExplanationSource {
  llm('llm'),
  template('template');

  const ExplanationSource(this.apiValue);
  final String apiValue;

  static ExplanationSource fromApi(String? value) =>
      values.firstWhere((s) => s.apiValue == value, orElse: () => template);
}
