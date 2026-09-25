import 'json_helpers.dart';

/// One entry of `GET /categories`. Send [id] as `food_category`.
class FoodCategory {
  const FoodCategory({required this.id, required this.name});

  factory FoodCategory.fromJson(Json json) =>
      FoodCategory(id: json['id'] as String, name: json['name'] as String);

  final String id;

  /// Label for the dropdown.
  final String name;
}
