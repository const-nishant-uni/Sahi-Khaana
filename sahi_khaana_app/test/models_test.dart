import 'package:flutter_test/flutter_test.dart';
import 'package:sahi_khaana_app/models/models.dart';

import 'helpers.dart';

void main() {
  group('ScanResult from a real /scan response', () {
    final scan = ScanResult.fromJson(fixture('scan.json'));

    test('top-level fields', () {
      expect(scan.scanId, '6e50b23f-d4c0-41b4-8793-e0ba8c61c2b8');
      expect(scan.createdAt, DateTime.utc(2026, 9, 25, 11, 3, 54, 997, 690));
      expect(scan.createdAt.isUtc, isTrue);
      expect(scan.status, 'ok');
      expect(scan.foodCategory, 'cereals_noodles');
      expect(scan.warnings, isEmpty);
    });

    test('ocr, including a non-ASCII character', () {
      expect(scan.ocr, isNotNull);
      expect(scan.ocr!.engine, 'rapidocr');
      expect(scan.ocr!.confidence, 0.9513);
      expect(scan.ocr!.rawText, contains('（')); // full-width bracket survives
    });

    test('ingredients', () {
      expect(scan.ingredients, hasLength(9));
      final flour = scan.ingredients.first;
      expect(flour.id, 'ing_1');
      expect(flour.original, 'Refined wheat flour (72%)');
      expect(flour.normalized, 'wheat flour');
      expect(flour.percentage, 72.0);
      expect(flour.insNumber, isNull);
      expect(flour.known, isTrue);
      expect(flour.repaired, isFalse);
      expect(flour.displayName, 'wheat flour');

      final acid = scan.ingredients[4];
      expect(acid.insNumber, '501(i)');
      expect(acid.category, 'acidity_regulator');
      expect(acid.matchConfidence, 1.0);
    });

    test('nutrition: values, nulls, basis', () {
      final n = scan.nutrition;
      expect(n.basis, NutritionBasis.per100g);
      expect(n.sodiumMg, 1240.0);
      expect(n.totalFatG, 17.5);
      expect(n.energyKcal, isNull); // this scan did not read an energy value
      expect(n.fiberG, isNull);
      expect(n.isEmpty, isFalse);
    });

    test('fssai_result', () {
      final f = scan.fssaiResult;
      expect(f.overallStatus, FssaiStatus.review);
      expect(f.summary.scanned, 9);
      expect(f.summary.pass, 4); // JSON key "pass"
      expect(f.summary.flag, 0);
      expect(f.summary.review, 5);
      expect(f.summary.pass + f.summary.flag + f.summary.review, f.summary.scanned);
      expect(f.confidence, 0.9513);
      expect(f.findings, hasLength(10));
    });

    test('a label-level finding has a null ingredient id', () {
      final labelLevel = scan.fssaiResult.labelLevelFindings;
      expect(labelLevel, hasLength(1));
      expect(labelLevel.single.ingredientId, isNull);
      expect(labelLevel.single.isLabelLevel, isTrue);
      expect(labelLevel.single.status, FssaiStatus.review);
      expect(labelLevel.single.reason, 'Declaration not found in the scanned area');
    });

    test('findings for one ingredient', () {
      final findings = scan.fssaiResult.findingsFor('ing_8');
      expect(findings, hasLength(1));
      expect(findings.single.status, FssaiStatus.review);
      expect(findings.single.source, startsWith('TODO:')); // unverified rule
      expect(scan.fssaiResult.findingsFor('nope'), isEmpty);
    });

    test('health_result: string completeness + numeric completeness_score', () {
      final h = scan.healthResult;
      expect(h.score, 60);
      expect(h.assessment, HealthAssessment.moderate);
      expect(h.dataCompleteness, DataCompleteness.full);
      expect(h.completenessScore, 0.88);
      expect(h.factors.map((f) => f.key), ['medium_total_fat', 'high_sat_fat', 'high_sodium']);
      expect(h.factors.first.type, HealthFactorType.nutrient);
      expect(h.factors.first.impact, -5.0);
      expect(h.disclaimer, isNotEmpty);
    });
  });

  group('/analyze response with a repaired ingredient', () {
    final result = ScanResult.fromJson(fixture('analyze_repaired.json'));

    test('ocr is null for typed text', () => expect(result.ocr, isNull));

    test('original stays raw, repaired is true, normalized holds the match', () {
      final first = result.ingredients.first;
      expect(first.original, 'Refinedwheatflour (72%)');
      expect(first.normalized, 'wheat flour');
      expect(first.repaired, isTrue);
      expect(result.ingredients.skip(1).every((i) => !i.repaired), isTrue);
    });

    test('assessment and category', () {
      expect(result.foodCategory, 'bakery');
      expect(result.healthResult.assessment, HealthAssessment.fewerConcerns);
    });
  });

  group('/mock/scan', () {
    final mock = ScanResult.fromJson(fixture('mock_scan.json'));

    test('parses, with a repaired ingredient and a label-level finding', () {
      expect(mock.ingredients.any((i) => i.repaired), isTrue);
      expect(mock.fssaiResult.labelLevelFindings, isNotEmpty);
      expect(mock.fssaiResult.overallStatus, FssaiStatus.flag);
      expect(mock.hasWarning('MOCK_DATA'), isTrue);
    });
  });

  group('history and explanation', () {
    test('ScanPage', () {
      final page = ScanPage.fromJson(fixture('scans_page.json'));
      expect(page.items, hasLength(2));
      expect(page.total, 2);
      expect(page.limit, 20);
      expect(page.offset, 0);
      expect(page.hasMore, isFalse);
      final first = page.items.first;
      expect(first.overallStatus, FssaiStatus.pass);
      expect(first.assessment, HealthAssessment.fewerConcerns);
      expect(first.healthScore, 90);
      expect(first.ingredientCount, 3);
      expect(first.foodCategory, 'bakery');
    });

    test('ScanPage paging maths', () {
      final page = ScanPage.fromJson({
        'items': [_summaryJson('a'), _summaryJson('b')],
        'total': 5,
        'limit': 2,
        'offset': 2,
      });
      expect(page.hasMore, isTrue);
      expect(page.nextOffset, 4);
    });

    test('Explanation', () {
      final e = Explanation.fromJson(fixture('explanation.json'));
      expect(e.source, ExplanationSource.template);
      expect(e.text, startsWith('FSSAI rule check:'));
    });

    test('FoodCategory', () {
      final c = FoodCategory.fromJson({'id': 'bakery', 'name': 'Bread, biscuits & bakery'});
      expect((c.id, c.name), ('bakery', 'Bread, biscuits & bakery'));
    });
  });

  group('robustness', () {
    test('unknown enum strings fall back to the SAFE value', () {
      expect(FssaiStatus.fromApi('NEW_STATUS'), FssaiStatus.review);
      expect(FssaiStatus.fromApi(null), FssaiStatus.review);
      expect(HealthAssessment.fromApi('??'), HealthAssessment.moderate);
      expect(DataCompleteness.fromApi('??'), DataCompleteness.ingredientsOnly);
      expect(ExplanationSource.fromApi('??'), ExplanationSource.template);
      expect(NutritionBasis.fromApi('per_pack'), isNull);
    });

    test('every enum round-trips its API string', () {
      for (final s in FssaiStatus.values) {
        expect(FssaiStatus.fromApi(s.apiValue), s);
      }
      for (final a in HealthAssessment.values) {
        expect(HealthAssessment.fromApi(a.apiValue), a);
      }
      for (final c in DataCompleteness.values) {
        expect(DataCompleteness.fromApi(c.apiValue), c);
      }
      expect(HealthAssessment.fewerConcerns.apiValue, 'FEWER CONCERNS');
      expect(DataCompleteness.ingredientsOnly.apiValue, 'ingredients_only');
    });

    test('an ingredient without "repaired" (older data) defaults to false', () {
      final json = Map<String, dynamic>.from(fixture('scan.json')['ingredients'][0] as Map)
        ..remove('repaired');
      expect(Ingredient.fromJson(json).repaired, isFalse);
    });

    test('ints and doubles are both accepted for numbers', () {
      final n = Nutrition.fromJson({'sodium_mg': 900, 'sugar_g': 3.4});
      expect((n.sodiumMg, n.sugarG), (900.0, 3.4));
      expect(Nutrition.fromJson({}).isEmpty, isTrue);
    });

    test('a missing required field throws (turned into BAD_RESPONSE by SahiApi)', () {
      final broken = Map<String, dynamic>.from(fixture('scan.json'))..remove('fssai_result');
      expect(() => ScanResult.fromJson(broken), throwsA(anything));
    });
  });

  group('warnings', () {
    ScanResult withWarnings(List<String> w) =>
        ScanResult.fromJson({...fixture('scan.json'), 'warnings': w});

    test('hasWarning matches the code and ignores any ":suffix"', () {
      final r = withWarnings([
        'LOW_OCR_CONFIDENCE',
        'IMPLAUSIBLE_NUTRIENT_IGNORED:total_fat_g',
        'IMPLAUSIBLE_NUTRIENT_IGNORED:sugar_g',
      ]);
      expect(r.hasWarning(ScanWarnings.lowOcrConfidence), isTrue);
      expect(r.hasWarning(ScanWarnings.implausibleNutrientIgnored), isTrue);
      expect(r.hasWarning(ScanWarnings.limitedNutritionData), isFalse);
      expect(r.ignoredNutrientFields, ['total_fat_g', 'sugar_g']);
    });

    test('codeOf', () {
      expect(ScanWarnings.codeOf('IMPLAUSIBLE_NUTRIENT_IGNORED:x'), 'IMPLAUSIBLE_NUTRIENT_IGNORED');
      expect(ScanWarnings.codeOf('LIMITED_NUTRITION_DATA'), 'LIMITED_NUTRITION_DATA');
    });
  });

  group('AnalyzeRequest', () {
    test('only provided fields are sent', () {
      expect(
        AnalyzeRequest(ingredientsText: 'Sugar, Salt', foodCategory: 'bakery').toJson(),
        {'ingredients_text': 'Sugar, Salt', 'food_category': 'bakery'},
      );
      expect(
        AnalyzeRequest(ingredients: ['Sugar'], nutritionText: 'Sodium 5 mg').toJson(),
        {'ingredients': ['Sugar'], 'nutrition_text': 'Sodium 5 mg'},
      );
    });

    test('needs ingredients text or a non-empty list', () {
      expect(() => AnalyzeRequest(), throwsArgumentError);
      expect(() => AnalyzeRequest(ingredientsText: '   '), throwsArgumentError);
      expect(() => AnalyzeRequest(ingredients: []), throwsArgumentError);
      expect(() => AnalyzeRequest(ingredients: [' ', '']), throwsArgumentError);
      expect(() => AnalyzeRequest(nutritionText: 'only nutrition'), throwsArgumentError);
    });

    test('enforces the backend limits', () {
      expect(() => AnalyzeRequest(ingredientsText: 'x' * 5001), throwsArgumentError);
      expect(AnalyzeRequest(ingredientsText: 'x' * 5000).ingredientsText, hasLength(5000));
      expect(() => AnalyzeRequest(ingredients: List.filled(101, 'a')), throwsArgumentError);
      expect(() => AnalyzeRequest(ingredientsText: 'a', nutritionText: 'x' * 3001), throwsArgumentError);
    });
  });
}

Map<String, dynamic> _summaryJson(String id) => {
  'scan_id': id,
  'created_at': '2026-09-25T11:03:55.010033+00:00',
  'food_category': null,
  'overall_status': 'REVIEW',
  'health_score': 50,
  'assessment': 'MODERATE',
  'ingredient_count': 1,
};
