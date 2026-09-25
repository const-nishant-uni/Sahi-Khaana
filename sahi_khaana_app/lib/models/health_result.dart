import 'enums.dart';
import 'json_helpers.dart';

/// One entry of `health_result.factors[]`.
class HealthFactor {
  const HealthFactor({
    required this.key,
    required this.type,
    required this.impact,
    required this.label,
    required this.detail,
  });

  factory HealthFactor.fromJson(Json json) => HealthFactor(
    key: json['key'] as String,
    type: HealthFactorType.fromApi(json['type'] as String?),
    impact: asDouble(json['impact']),
    label: json['label'] as String,
    detail: json['detail'] as String,
  );

  /// Stable id, e.g. "high_sodium".
  final String key;
  final HealthFactorType type;

  /// Score points: negative = concern, positive = good.
  final double impact;
  final String label;
  final String detail;
}

/// `health_result`: a configurable score. General information, not medical advice.
class HealthResult {
  const HealthResult({
    required this.score,
    required this.assessment,
    required this.dataCompleteness,
    required this.completenessScore,
    required this.factors,
    required this.disclaimer,
  });

  factory HealthResult.fromJson(Json json) => HealthResult(
    score: (json['score'] as num).toInt(),
    assessment: HealthAssessment.fromApi(json['assessment'] as String?),
    dataCompleteness: DataCompleteness.fromApi(
      json['data_completeness'] as String?,
    ),
    completenessScore: asDouble(json['completeness_score']),
    factors: asObjectList(json['factors'], HealthFactor.fromJson),
    disclaimer: json['disclaimer'] as String,
  );

  /// 0..100.
  final int score;

  /// Capped at MODERATE whenever there is no usable per-100 g nutrition data.
  final HealthAssessment assessment;
  final DataCompleteness dataCompleteness;

  /// 0..1 numeric version of [dataCompleteness].
  final double completenessScore;
  final List<HealthFactor> factors;

  /// Always show this next to the result.
  final String disclaimer;
}
