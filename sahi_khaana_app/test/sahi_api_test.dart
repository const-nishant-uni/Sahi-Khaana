import 'dart:io';
import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:sahi_khaana_app/api/api.dart';
import 'package:sahi_khaana_app/models/models.dart';

import 'helpers.dart';

void main() {
  group('each endpoint: method, path, parsing', () {
    test('GET /health', () async {
      final t = fakeApi((r) async => jsonResponse({'status': 'ok', 'version': '0.1.0'}));
      expect(await t.api.health(), '0.1.0');
      expect((t.seen.single.method, t.seen.single.url.path), ('GET', '/api/v1/health'));
    });

    test('GET /categories', () async {
      final t = fakeApi((r) async => jsonResponse({
            'categories': [
              {'id': 'bakery', 'name': 'Bread, biscuits & bakery'},
              {'id': 'other', 'name': 'Other'},
            ],
          }));
      final categories = await t.api.categories();
      expect(categories.map((c) => c.id), ['bakery', 'other']);
      expect((t.seen.single.method, t.seen.single.url.path), ('GET', '/api/v1/categories'));
    });

    test('POST /scan: multipart with field "image" and food_category', () async {
      final t = fakeApi((r) async => jsonResponse(fixture('scan.json')));
      final result = await t.api.scanBytes(
        Uint8List.fromList([0xff, 0xd8, 0xff, 0xe0]),
        filename: 'pack.jpg',
        foodCategory: 'cereals_noodles',
      );
      expect(result.scanId, '6e50b23f-d4c0-41b4-8793-e0ba8c61c2b8');
      final r = t.seen.single;
      expect((r.method, r.url.path), ('POST', '/api/v1/scan'));
      final body = String.fromCharCodes(r.bodyBytes);
      expect(body, contains('name="image"; filename="pack.jpg"'));
      expect(body, contains('name="food_category"'));
      expect(body, contains('cereals_noodles'));
    });

    test('POST /scan without a category sends no food_category field', () async {
      final t = fakeApi((r) async => jsonResponse(fixture('scan.json')));
      await t.api.scanBytes(Uint8List.fromList([1, 2, 3]), filename: 'a.png');
      expect(String.fromCharCodes(t.seen.single.bodyBytes), isNot(contains('food_category')));

      await t.api.scanBytes(Uint8List.fromList([1, 2, 3]), filename: 'a.png', foodCategory: '');
      expect(String.fromCharCodes(t.seen.last.bodyBytes), isNot(contains('food_category')));
    });

    test('scanFile reads the file and uses its name', () async {
      final dir = await Directory.systemTemp.createTemp('sahi_test');
      addTearDown(() => dir.delete(recursive: true));
      final file = File('${dir.path}/my_label.webp')..writeAsBytesSync([9, 8, 7]);
      final t = fakeApi((r) async => jsonResponse(fixture('scan.json')));
      await t.api.scanFile(file.path, foodCategory: 'dairy');
      final body = String.fromCharCodes(t.seen.single.bodyBytes);
      expect(body, contains('filename="my_label.webp"'));
      expect(body, contains('dairy'));
    });

    test('POST /analyze sends the JSON body', () async {
      final t = fakeApi((r) async => jsonResponse(fixture('analyze_repaired.json')));
      final result = await t.api.analyze(AnalyzeRequest(
        ingredientsText: 'Refinedwheatflour (72%), Sugar, Salt',
        nutritionText: 'per 100 g: Sodium 300 mg',
        foodCategory: 'bakery',
      ));
      expect(result.ingredients.first.repaired, isTrue);
      final r = t.seen.single;
      expect((r.method, r.url.path), ('POST', '/api/v1/analyze'));
      expect(r.body, contains('"ingredients_text":"Refinedwheatflour (72%), Sugar, Salt"'));
      expect(r.body, contains('"food_category":"bakery"'));
    });

    test('GET /scans with limit and offset (defaults 20 and 0)', () async {
      final t = fakeApi((r) async => jsonResponse(fixture('scans_page.json')));
      final page = await t.api.listScans();
      expect(page.items, hasLength(2));
      expect(t.seen.last.url.queryParameters, {'limit': '20', 'offset': '0'});

      await t.api.listScans(limit: 5, offset: 10);
      expect(t.seen.last.url.path, '/api/v1/scans');
      expect(t.seen.last.url.queryParameters, {'limit': '5', 'offset': '10'});
    });

    test('listScans rejects a bad limit or offset without calling the server', () {
      final t = fakeApi((r) async => jsonResponse(fixture('scans_page.json')));
      expect(() => t.api.listScans(limit: 0), throwsRangeError);
      expect(() => t.api.listScans(limit: 101), throwsRangeError);
      expect(() => t.api.listScans(offset: -1), throwsRangeError);
      expect(t.seen, isEmpty);
    });

    test('GET /scans/{id}', () async {
      final t = fakeApi((r) async => jsonResponse(fixture('scan.json')));
      final scan = await t.api.getScan('abc-123');
      expect(scan.healthResult.score, 60);
      expect((t.seen.single.method, t.seen.single.url.path), ('GET', '/api/v1/scans/abc-123'));
    });

    test('the id is URL-encoded', () async {
      final t = fakeApi((r) async => errorResponse(404, ApiErrorCodes.scanNotFound));
      await expectLater(t.api.getScan('a/b c'), throwsA(isA<ApiException>()));
      expect(t.seen.single.url.toString(), 'http://test.local/api/v1/scans/a%2Fb%20c');
    });

    test('DELETE /scans/{id} succeeds on an empty 204', () async {
      final t = fakeApi((r) async => http.Response('', 204));
      await t.api.deleteScan('abc-123');
      expect((t.seen.single.method, t.seen.single.url.path), ('DELETE', '/api/v1/scans/abc-123'));
    });

    test('GET /scans/{id}/explanation', () async {
      final t = fakeApi((r) async => jsonResponse(fixture('explanation.json')));
      final e = await t.api.explanation('abc-123');
      expect(e.source, ExplanationSource.template);
      expect(t.seen.single.url.path, '/api/v1/scans/abc-123/explanation');
    });

    test('GET /mock/scan', () async {
      final t = fakeApi((r) async => jsonResponse(fixture('mock_scan.json')));
      final mock = await t.api.mockScan();
      expect(mock.ingredients, isNotEmpty);
      expect(t.seen.single.url.path, '/api/v1/mock/scan');
    });

    test('every call carries the device id', () async {
      final t = fakeApi((r) async => jsonResponse(fixture('scans_page.json')));
      await t.api.listScans();
      expect(t.seen.single.headers['X-Device-Id'], testDeviceId);
    });
  });

  group('errors', () {
    test('POOR_IMAGE on scan -> isRetakePhoto', () async {
      final t = fakeApi((r) async => errorResponse(422, ApiErrorCodes.poorImage, 'too blurry'));
      await expectLater(
        t.api.scanBytes(Uint8List(3), filename: 'a.jpg'),
        throwsA(isA<ApiException>()
            .having((e) => e.isRetakePhoto, 'isRetakePhoto', isTrue)
            .having((e) => e.statusCode, 'statusCode', 422)),
      );
    });

    test('deleting an unknown scan -> SCAN_NOT_FOUND', () async {
      final t = fakeApi((r) async => errorResponse(404, ApiErrorCodes.scanNotFound));
      await expectLater(
        t.api.deleteScan('nope'),
        throwsA(isA<ApiException>().having((e) => e.isScanNotFound, 'isScanNotFound', isTrue)),
      );
    });

    test('a 200 with the wrong JSON shape -> BAD_RESPONSE (never a TypeError)', () async {
      final broken = Map<String, dynamic>.from(fixture('scan.json'))..remove('health_result');
      final t = fakeApi((r) async => jsonResponse(broken));
      await expectLater(
        t.api.getScan('x'),
        throwsA(isA<ApiException>().having((e) => e.code, 'code', ApiErrorCodes.badResponse)),
      );
    });

    test('a JSON array where an object is expected -> BAD_RESPONSE', () async {
      final t = fakeApi((r) async => http.Response('[1,2]', 200));
      await expectLater(
        t.api.health(),
        throwsA(isA<ApiException>().having((e) => e.code, 'code', ApiErrorCodes.badResponse)),
      );
    });

    test('an empty 200 for a call that needs data -> BAD_RESPONSE', () async {
      final t = fakeApi((r) async => http.Response('', 200));
      await expectLater(
        t.api.categories(),
        throwsA(isA<ApiException>().having((e) => e.code, 'code', ApiErrorCodes.badResponse)),
      );
    });

    test('offline -> NETWORK_ERROR from any endpoint', () async {
      final t = fakeApi((r) async => throw const SocketException('no route'));
      await expectLater(
        t.api.categories(),
        throwsA(isA<ApiException>().having((e) => e.isNetworkProblem, 'isNetworkProblem', isTrue)),
      );
    });
  });
}
