import 'enums.dart';
import 'json_helpers.dart';

/// `nutrition`. Every value can be null (not found on the label). Never 0 for "missing".
class Nutrition {
  const Nutrition({
    this.basis,
    this.energyKcal,
    this.sugarG,
    this.sodiumMg,
    this.satFatG,
    this.transFatG,
    this.totalFatG,
    this.proteinG,
    this.fiberG,
  });

  factory Nutrition.fromJson(Json json) => Nutrition(
    basis: NutritionBasis.fromApi(json['basis'] as String?),
    energyKcal: asDoubleOrNull(json['energy_kcal']),
    sugarG: asDoubleOrNull(json['sugar_g']),
    sodiumMg: asDoubleOrNull(json['sodium_mg']),
    satFatG: asDoubleOrNull(json['sat_fat_g']),
    transFatG: asDoubleOrNull(json['trans_fat_g']),
    totalFatG: asDoubleOrNull(json['total_fat_g']),
    proteinG: asDoubleOrNull(json['protein_g']),
    fiberG: asDoubleOrNull(json['fiber_g']),
  );

  final NutritionBasis? basis;

  /// Always kcal.
  final double? energyKcal;
  final double? sugarG;

  /// Always mg.
  final double? sodiumMg;
  final double? satFatG;
  final double? transFatG;
  final double? totalFatG;
  final double? proteinG;
  final double? fiberG;

  /// True when no nutrient value was found at all.
  bool get isEmpty =>
      energyKcal == null &&
      sugarG == null &&
      sodiumMg == null &&
      satFatG == null &&
      transFatG == null &&
      totalFatG == null &&
      proteinG == null &&
      fiberG == null;
}
