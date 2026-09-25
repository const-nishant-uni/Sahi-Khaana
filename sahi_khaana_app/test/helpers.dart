import 'dart:convert';
import 'dart:io';

import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:sahi_khaana_app/api/api.dart';
import 'package:sahi_khaana_app/services/device_id_store.dart';

/// A real backend response saved in test/fixtures (see docs/API_CHANGES.md in the backend).
Map<String, dynamic> fixture(String name) =>
    jsonDecode(File('test/fixtures/$name').readAsStringSync())
        as Map<String, dynamic>;

/// A JSON response, encoded as UTF-8 with NO charset in the content type (what FastAPI sends).
http.Response jsonResponse(Object body, [int status = 200]) => http.Response.bytes(
  utf8.encode(jsonEncode(body)),
  status,
  headers: {'content-type': 'application/json'},
);

/// The backend's error shape: {"error": {"code", "message"}}.
http.Response errorResponse(int status, String code, [String message = 'msg']) =>
    jsonResponse({
      'error': {'code': code, 'message': message},
    }, status);

const testDeviceId = '3f0c2c5e-8a4b-4c6f-9d1e-2b7a5e9c1d34';

/// A [SahiApi] wired to a fake HTTP handler. [seen] collects every request sent.
({SahiApi api, List<http.Request> seen}) fakeApi(
  Future<http.Response> Function(http.Request request) handler, {
  ApiConfig config = const ApiConfig(baseUrl: 'http://test.local/api/v1'),
}) {
  final seen = <http.Request>[];
  final client = MockClient((request) {
    seen.add(request);
    return handler(request);
  });
  final api = SahiApi(
    ApiClient(
      config: config,
      deviceIdStore: InMemoryDeviceIdStore(testDeviceId),
      httpClient: client,
    ),
  );
  return (api: api, seen: seen);
}
