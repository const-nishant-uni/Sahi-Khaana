import 'enums.dart';
import 'json_helpers.dart';

/// One row of `GET /scans`. The full result is at `GET /scans/{id}`.
class ScanSummary {
  const ScanSummary({
    required this.scanId,
    required this.createdAt,
    required this.foodCategory,
    required this.overallStatus,
    required this.healthScore,
    required this.assessment,
    required this.ingredientCount,
  });

  factory ScanSummary.fromJson(Json json) => ScanSummary(
    scanId: json['scan_id'] as String,
    createdAt: DateTime.parse(json['created_at'] as String),
    foodCategory: json['food_category'] as String?,
    overallStatus: FssaiStatus.fromApi(json['overall_status'] as String?),
    healthScore: (json['health_score'] as num).toInt(),
    assessment: HealthAssessment.fromApi(json['assessment'] as String?),
    ingredientCount: (json['ingredient_count'] as num).toInt(),
  );

  final String scanId;
  final DateTime createdAt;
  final String? foodCategory;
  final FssaiStatus overallStatus;
  final int healthScore;
  final HealthAssessment assessment;
  final int ingredientCount;
}

/// `GET /scans`: one page of history, newest first, for this device only.
class ScanPage {
  const ScanPage({
    required this.items,
    required this.total,
    required this.limit,
    required this.offset,
  });

  factory ScanPage.fromJson(Json json) => ScanPage(
    items: asObjectList(json['items'], ScanSummary.fromJson),
    total: (json['total'] as num).toInt(),
    limit: (json['limit'] as num).toInt(),
    offset: (json['offset'] as num).toInt(),
  );

  final List<ScanSummary> items;

  /// All scans for this device (for paging).
  final int total;
  final int limit;
  final int offset;

  /// True while there are more pages after this one.
  bool get hasMore => offset + items.length < total;

  /// The `offset` to request for the next page.
  int get nextOffset => offset + items.length;
}
