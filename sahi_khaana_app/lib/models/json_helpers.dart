/// Small helpers for reading JSON safely. A wrong type throws a [TypeError] /
/// [FormatException]; `SahiApi` turns that into an `ApiException` (BAD_RESPONSE).
library;

typedef Json = Map<String, dynamic>;

/// JSON numbers arrive as int or double; always give back a double.
double asDouble(Object? value) => (value as num).toDouble();

double? asDoubleOrNull(Object? value) =>
    value == null ? null : (value as num).toDouble();

/// Reads a JSON list of objects with [fromJson]. A missing/null list becomes empty.
List<T> asObjectList<T>(Object? value, T Function(Json json) fromJson) {
  if (value == null) return const [];
  return List<T>.unmodifiable(
    (value as List).map((e) => fromJson(e as Json)),
  );
}

List<String> asStringList(Object? value) {
  if (value == null) return const [];
  return List<String>.unmodifiable((value as List).cast<String>());
}
