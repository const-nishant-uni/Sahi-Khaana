import 'enums.dart';
import 'json_helpers.dart';

/// `GET /scans/{id}/explanation`.
class Explanation {
  const Explanation({required this.text, required this.source});

  factory Explanation.fromJson(Json json) => Explanation(
    text: json['explanation'] as String,
    source: ExplanationSource.fromApi(json['source'] as String?),
  );

  /// Plain-English text. Never changes any status.
  final String text;

  /// [ExplanationSource.llm] = worded by an AI; [ExplanationSource.template] = built
  /// directly from the rule results (no key, or the AI call failed).
  final ExplanationSource source;
}
