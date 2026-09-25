import 'enums.dart';
import 'json_helpers.dart';

/// `fssai_result.summary`. Counts ingredients only: pass + flag + review == scanned.
class FssaiSummary {
  const FssaiSummary({
    required this.scanned,
    required this.matched,
    required this.pass,
    required this.flag,
    required this.review,
  });

  factory FssaiSummary.fromJson(Json json) => FssaiSummary(
    scanned: json['scanned'] as int,
    matched: json['matched'] as int,
    pass: json['pass'] as int, // the JSON key really is "pass"
    flag: json['flag'] as int,
    review: json['review'] as int,
  );

  final int scanned;
  final int matched;
  final int pass;
  final int flag;
  final int review;
}

/// One entry of `fssai_result.findings[]`.
class Finding {
  const Finding({
    required this.ingredientId,
    required this.ruleId,
    required this.status,
    required this.reason,
    required this.source,
  });

  factory Finding.fromJson(Json json) => Finding(
    ingredientId: json['ingredient_id'] as String?,
    ruleId: json['rule_id'] as String,
    status: FssaiStatus.fromApi(json['status'] as String?),
    reason: json['reason'] as String,
    source: json['source'] as String,
  );

  /// Null for a LABEL-LEVEL finding (e.g. a required declaration was not found).
  final String? ingredientId;
  final String ruleId;
  final FssaiStatus status;
  final String reason;

  /// Where the rule comes from. Starts with "TODO:" while the rule is unverified.
  final String source;

  bool get isLabelLevel => ingredientId == null;
}

/// `fssai_result`: the deterministic rule check. Never produced by AI.
class FssaiResult {
  const FssaiResult({
    required this.overallStatus,
    required this.summary,
    required this.confidence,
    required this.findings,
  });

  factory FssaiResult.fromJson(Json json) => FssaiResult(
    overallStatus: FssaiStatus.fromApi(json['overall_status'] as String?),
    summary: FssaiSummary.fromJson(json['summary'] as Json),
    confidence: asDouble(json['confidence']),
    findings: asObjectList(json['findings'], Finding.fromJson),
  );

  /// Any FLAG gives flag; else any REVIEW (ingredient or label-level) gives review; else pass.
  /// It can be [FssaiStatus.review] while `summary.review == 0` (a label-level finding).
  final FssaiStatus overallStatus;
  final FssaiSummary summary;

  /// 0..1: OCR confidence x share of ingredients recognised.
  final double confidence;
  final List<Finding> findings;

  /// Findings that belong to the whole label rather than to one ingredient.
  List<Finding> get labelLevelFindings =>
      findings.where((f) => f.isLabelLevel).toList(growable: false);

  /// Findings for one ingredient (matches `Ingredient.id`).
  List<Finding> findingsFor(String ingredientId) => findings
      .where((f) => f.ingredientId == ingredientId)
      .toList(growable: false);
}
