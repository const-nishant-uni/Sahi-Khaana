/// Body of `POST /analyze`. Give [ingredientsText] OR [ingredients]; the rest is optional.
class AnalyzeRequest {
  AnalyzeRequest({
    this.ingredientsText,
    this.ingredients,
    this.nutritionText,
    this.foodCategory,
  }) {
    final hasText = ingredientsText?.trim().isNotEmpty ?? false;
    final hasList = ingredients?.any((i) => i.trim().isNotEmpty) ?? false;
    if (!hasText && !hasList) {
      throw ArgumentError(
        'Provide ingredientsText or a non-empty ingredients list.',
      );
    }
    if ((ingredientsText?.length ?? 0) > maxIngredientsTextLength) {
      throw ArgumentError('ingredientsText is longer than $maxIngredientsTextLength characters.');
    }
    if ((ingredients?.length ?? 0) > maxIngredientItems) {
      throw ArgumentError('More than $maxIngredientItems ingredients.');
    }
    if ((nutritionText?.length ?? 0) > maxNutritionTextLength) {
      throw ArgumentError('nutritionText is longer than $maxNutritionTextLength characters.');
    }
  }

  // Limits enforced by the backend.
  static const maxIngredientsTextLength = 5000;
  static const maxIngredientItems = 100;
  static const maxNutritionTextLength = 3000;

  final String? ingredientsText;
  final List<String>? ingredients;
  final String? nutritionText;

  /// A `FoodCategory.id` from `GET /categories`.
  final String? foodCategory;

  /// Only the fields that were provided (the backend treats missing and null alike).
  Map<String, dynamic> toJson() => {
    if (ingredientsText != null) 'ingredients_text': ingredientsText,
    if (ingredients != null) 'ingredients': ingredients,
    if (nutritionText != null) 'nutrition_text': nutritionText,
    if (foodCategory != null) 'food_category': foodCategory,
  };
}
