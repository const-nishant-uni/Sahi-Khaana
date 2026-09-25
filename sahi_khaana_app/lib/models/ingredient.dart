import 'json_helpers.dart';

/// One entry of `ingredients[]`.
class Ingredient {
  const Ingredient({
    required this.id,
    required this.original,
    required this.normalized,
    required this.category,
    required this.insNumber,
    required this.percentage,
    required this.matchConfidence,
    required this.known,
    required this.repaired,
  });

  factory Ingredient.fromJson(Json json) => Ingredient(
    id: json['id'] as String,
    original: json['original'] as String,
    normalized: json['normalized'] as String?,
    category: json['category'] as String?,
    insNumber: json['ins_number'] as String?,
    percentage: asDoubleOrNull(json['percentage']),
    matchConfidence: asDouble(json['match_confidence']),
    known: json['known'] as bool,
    // Absent in data stored before the field existed.
    repaired: json['repaired'] as bool? ?? false,
  );

  /// "ing_1", "ing_2", ... (what `Finding.ingredientId` refers to).
  final String id;

  /// The raw OCR token, exactly as read (may be run together: "Refinedwheatflour").
  final String original;

  /// Name of the matched rule entry, or null if the ingredient is unknown.
  final String? normalized;
  final String? category;

  /// e.g. "211", "501(i)".
  final String? insNumber;
  final double? percentage;
  final double matchConfidence;

  /// False if the ingredient was not found in the backend's rule data.
  final bool known;

  /// True if OCR ran words together and the backend recovered the match by splitting them.
  final bool repaired;

  /// [normalized] when known, otherwise the raw text. Handy as a label.
  String get displayName => normalized ?? original;
}
