import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:sahi_khaana_app/api/api.dart';
import 'package:sahi_khaana_app/services/device_id_store.dart';

import 'helpers.dart';

ApiClient clientFor(
  Future<http.Response> Function(http.Request) handler, {
  ApiConfig config = const ApiConfig(baseUrl: 'http://test.local/api/v1'),
  DeviceIdStore? store,
}) => ApiClient(
  config: config,
  deviceIdStore: store ?? InMemoryDeviceIdStore(testDeviceId),
  httpClient: MockClient(handler),
);

void main() {
  group('X-Device-Id header', () {
    test('is sent on GET, POST json, DELETE and multipart', () async {
      final seen = <http.Request>[];
      final client = clientFor((r) async {
        seen.add(r);
        return jsonResponse({'ok': true});
      });
      await client.getJson('/health');
      await client.postJson('/analyze', {'a': 1});
      await client.delete('/scans/x');
      await client.postMultipart('/scan', fileField: 'image', fileBytes: [1, 2, 3], filename: 'a.jpg');

      expect(seen, hasLength(4));
      for (final r in seen) {
        expect(r.headers['X-Device-Id'], testDeviceId, reason: '${r.method} ${r.url}');
        expect(r.headers['Accept'], 'application/json');
      }
    });

    test('the id is created once and reused for every call', () async {
      final store = InMemoryDeviceIdStore(); // no id yet
      final ids = <String>{};
      final client = clientFor((r) async {
        ids.add(r.headers['X-Device-Id']!);
        return jsonResponse({});
      }, store: store);
      for (var i = 0; i < 3; i++) {
        await client.getJson('/health');
      }
      expect(ids, hasLength(1));
      expect(uuidPattern.hasMatch(ids.single), isTrue);
      expect(await store.getOrCreate(), ids.single);
    });
  });

  group('requests', () {
    test('URL = baseUrl + path + query; a trailing slash on baseUrl is harmless', () async {
      late Uri seen;
      final client = clientFor((r) async {
        seen = r.url;
        return jsonResponse({});
      }, config: ApiConfig(baseUrl: ApiConfig.resolveBaseUrl(override: 'http://h:8000/api/v1/', isAndroid: false)));
      await client.getJson('/scans', query: {'limit': '5', 'offset': '10'});
      expect(seen.toString(), 'http://h:8000/api/v1/scans?limit=5&offset=10');
    });

    test('POST json sets content type and encodes the body as JSON', () async {
      late http.Request seen;
      final client = clientFor((r) async {
        seen = r;
        return jsonResponse({});
      });
      await client.postJson('/analyze', {'ingredients_text': 'Sugar (12%)'});
      expect(seen.method, 'POST');
      expect(seen.headers['Content-Type'], startsWith('application/json'));
      expect(jsonDecode(utf8.decode(seen.bodyBytes)), {'ingredients_text': 'Sugar (12%)'});
    });

    test('multipart carries the file under its field name plus text fields', () async {
      late http.Request seen;
      final client = clientFor((r) async {
        seen = r;
        return jsonResponse({});
      });
      await client.postMultipart(
        '/scan',
        fileField: 'image',
        fileBytes: [0xff, 0xd8, 0xff, 0x01],
        filename: 'label.jpg',
        fields: {'food_category': 'bakery'},
      );
      final body = latin1.decode(seen.bodyBytes);
      expect(seen.headers['content-type'], startsWith('multipart/form-data; boundary='));
      expect(body, contains('name="image"'));
      expect(body, contains('filename="label.jpg"'));
      expect(body, contains('name="food_category"'));
      expect(body, contains('bakery'));
      expect(seen.bodyBytes.contains(0xd8), isTrue); // the raw bytes are in there
    });
  });

  group('responses', () {
    test('2xx with JSON is decoded', () async {
      final client = clientFor((r) async => jsonResponse({'status': 'ok', 'n': 3}));
      expect(await client.getJson('/health'), {'status': 'ok', 'n': 3});
    });

    test('204 with an empty body is fine (DELETE)', () async {
      final client = clientFor((r) async => http.Response('', 204));
      await client.delete('/scans/x'); // does not throw
      expect(await client.getJson('/anything'), isNull);
    });

    test('UTF-8 is decoded even without a charset header', () async {
      // FastAPI sends "application/json" only; the http package would guess latin-1.
      final client = clientFor((r) async => http.Response.bytes(
            utf8.encode('{"t": "INS 211（sodium） µg é"}'),
            200,
            headers: {'content-type': 'application/json'},
          ));
      expect(await client.getJson('/x'), {'t': 'INS 211（sodium） µg é'});
    });

    test('2xx that is not JSON -> BAD_RESPONSE', () async {
      final client = clientFor((r) async => http.Response('<html>oops</html>', 200));
      await expectLater(
        client.getJson('/x'),
        throwsA(isA<ApiException>().having((e) => e.code, 'code', ApiErrorCodes.badResponse)),
      );
    });
  });

  group('backend errors -> ApiException(code)', () {
    final cases = <(int, String)>[
      (400, ApiErrorCodes.missingDeviceId),
      (400, ApiErrorCodes.invalidDeviceId),
      (400, ApiErrorCodes.invalidFile),
      (400, ApiErrorCodes.invalidCategory),
      (404, ApiErrorCodes.scanNotFound),
      (404, ApiErrorCodes.notFound),
      (405, ApiErrorCodes.methodNotAllowed),
      (413, ApiErrorCodes.fileTooLarge),
      (422, ApiErrorCodes.poorImage),
      (422, ApiErrorCodes.noTextFound),
      (422, ApiErrorCodes.noIngredientsSection),
      (422, ApiErrorCodes.validationError),
      (500, ApiErrorCodes.internalError),
    ];
    for (final (status, code) in cases) {
      test('$status $code', () async {
        final client = clientFor((r) async => errorResponse(status, code, 'the message'));
        await expectLater(
          client.getJson('/x'),
          throwsA(
            isA<ApiException>()
                .having((e) => e.code, 'code', code)
                .having((e) => e.statusCode, 'statusCode', status)
                .having((e) => e.message, 'message', 'the message'),
          ),
        );
      });
    }

    test('an error with a non-JSON body -> HTTP_ERROR with the status', () async {
      final client = clientFor((r) async => http.Response('Bad Gateway', 502));
      await expectLater(
        client.getJson('/x'),
        throwsA(isA<ApiException>()
            .having((e) => e.code, 'code', ApiErrorCodes.httpError)
            .having((e) => e.statusCode, 'status', 502)),
      );
    });

    test('an error with an empty body -> HTTP_ERROR', () async {
      final client = clientFor((r) async => http.Response('', 500));
      await expectLater(
        client.getJson('/x'),
        throwsA(isA<ApiException>().having((e) => e.code, 'code', ApiErrorCodes.httpError)),
      );
    });

    test('a JSON error in the wrong shape -> HTTP_ERROR', () async {
      final client = clientFor((r) async => jsonResponse({'detail': 'nope'}, 418));
      await expectLater(
        client.getJson('/x'),
        throwsA(isA<ApiException>()
            .having((e) => e.code, 'code', ApiErrorCodes.httpError)
            .having((e) => e.statusCode, 'status', 418)),
      );
    });

    test('helper getters', () {
      ApiException e(String code) => ApiException(code: code, message: '');
      expect(e(ApiErrorCodes.poorImage).isRetakePhoto, isTrue);
      expect(e(ApiErrorCodes.noTextFound).isRetakePhoto, isTrue);
      expect(e(ApiErrorCodes.noIngredientsSection).isRetakePhoto, isTrue);
      expect(e(ApiErrorCodes.fileTooLarge).isRetakePhoto, isFalse);
      expect(e(ApiErrorCodes.networkError).isNetworkProblem, isTrue);
      expect(e(ApiErrorCodes.timeout).isNetworkProblem, isTrue);
      expect(e(ApiErrorCodes.scanNotFound).isScanNotFound, isTrue);
      expect(e(ApiErrorCodes.scanNotFound).isNetworkProblem, isFalse);
    });
  });

  group('network problems', () {
    test('SocketException -> NETWORK_ERROR', () async {
      final client = clientFor((r) async => throw const SocketException('Connection refused'));
      await expectLater(
        client.getJson('/x'),
        throwsA(isA<ApiException>()
            .having((e) => e.code, 'code', ApiErrorCodes.networkError)
            .having((e) => e.isNetworkProblem, 'isNetworkProblem', isTrue)
            .having((e) => e.statusCode, 'statusCode', isNull)),
      );
    });

    test('http.ClientException -> NETWORK_ERROR', () async {
      final client = clientFor((r) async => throw http.ClientException('Connection closed'));
      await expectLater(
        client.getJson('/x'),
        throwsA(isA<ApiException>().having((e) => e.code, 'code', ApiErrorCodes.networkError)),
      );
    });

    test('a slow server -> TIMEOUT', () async {
      final client = clientFor(
        (r) async {
          await Future<void>.delayed(const Duration(milliseconds: 300));
          return jsonResponse({});
        },
        config: const ApiConfig(baseUrl: 'http://t/api/v1', requestTimeout: Duration(milliseconds: 30)),
      );
      await expectLater(
        client.getJson('/x'),
        throwsA(isA<ApiException>()
            .having((e) => e.code, 'code', ApiErrorCodes.timeout)
            .having((e) => e.isNetworkProblem, 'isNetworkProblem', isTrue)),
      );
    });

    test('uploads get the longer scanTimeout, other calls the shorter one', () async {
      Future<http.Response> slow(http.Request r) async {
        await Future<void>.delayed(const Duration(milliseconds: 150));
        return jsonResponse({});
      }

      final client = clientFor(
        slow,
        config: const ApiConfig(
          baseUrl: 'http://t/api/v1',
          requestTimeout: Duration(milliseconds: 30),
          scanTimeout: Duration(seconds: 2),
        ),
      );
      await client.postMultipart('/scan', fileField: 'image', fileBytes: [1], filename: 'a.jpg'); // ok
      await expectLater(client.getJson('/x'), throwsA(isA<ApiException>()));
    });

    test('nothing but ApiException escapes', () async {
      final client = clientFor((r) async => throw TimeoutException('x'));
      await expectLater(client.getJson('/x'), throwsA(isA<ApiException>()));
    });
  });
}
