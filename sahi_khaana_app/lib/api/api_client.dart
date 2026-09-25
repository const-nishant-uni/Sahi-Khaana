import 'dart:async';
import 'dart:convert';
import 'dart:io' show IOException;

import 'package:http/http.dart' as http;

import '../services/device_id_store.dart';
import 'api_config.dart';
import 'api_exception.dart';

/// Low-level HTTP for the Sahi Khaana backend. It adds the `X-Device-Id` header, applies
/// timeouts, decodes UTF-8 correctly and turns every failure into an [ApiException].
/// Use `SahiApi` (typed methods) instead of calling this directly.
class ApiClient {
  ApiClient({
    required this.config,
    required this.deviceIdStore,
    http.Client? httpClient,
  }) : _http = httpClient ?? http.Client();

  final ApiConfig config;
  final DeviceIdStore deviceIdStore;
  final http.Client _http;

  /// GET. Returns decoded JSON (or null for an empty body).
  Future<Object?> getJson(String path, {Map<String, String>? query}) =>
      _send(
        http.Request('GET', config.uri(path, query)),
        timeout: config.requestTimeout,
      );

  /// POST with a JSON body.
  Future<Object?> postJson(String path, Map<String, dynamic> body) =>
      _send(
        http.Request('POST', config.uri(path))
          ..headers['Content-Type'] = 'application/json; charset=utf-8'
          ..body = jsonEncode(body),
        timeout: config.requestTimeout,
      );

  /// DELETE. Success is an empty 204, so nothing is returned.
  Future<void> delete(String path) async {
    await _send(
      http.Request('DELETE', config.uri(path)),
      timeout: config.requestTimeout,
    );
  }

  /// POST multipart/form-data with one file and optional text fields.
  Future<Object?> postMultipart(
    String path, {
    required String fileField,
    required List<int> fileBytes,
    required String filename,
    Map<String, String> fields = const {},
  }) => _send(
    http.MultipartRequest('POST', config.uri(path))
      ..files.add(
        http.MultipartFile.fromBytes(fileField, fileBytes, filename: filename),
      )
      ..fields.addAll(fields),
    timeout: config.scanTimeout,
  );

  void close() => _http.close();

  Future<Object?> _send(
    http.BaseRequest request, {
    required Duration timeout,
  }) async {
    request.headers['Accept'] = 'application/json';
    request.headers['X-Device-Id'] = await deviceIdStore.getOrCreate();

    final http.Response response;
    try {
      // One deadline for the whole exchange (connect + server work + reading the body).
      response = await (() async {
        final streamed = await _http.send(request);
        return http.Response.fromStream(streamed);
      })().timeout(timeout);
    } on TimeoutException {
      throw ApiException.timeout(timeout);
    } on IOException catch (e) {
      // SocketException (no route, refused, DNS), TLS problems...
      throw ApiException.network(e);
    } on http.ClientException catch (e) {
      throw ApiException.network(e);
    }
    return _decode(response);
  }

  Object? _decode(http.Response response) {
    // Decode the bytes as UTF-8 ourselves: `response.body` would use latin-1 when the server
    // sends no charset, which garbles characters such as the full-width bracket "（".
    final text = utf8.decode(response.bodyBytes, allowMalformed: true).trim();
    final ok = response.statusCode >= 200 && response.statusCode < 300;

    Object? decoded;
    if (text.isNotEmpty) {
      try {
        decoded = jsonDecode(text);
      } on FormatException catch (e) {
        if (ok) throw ApiException.badResponse(e.message);
        // An error page that is not JSON (proxy, crash): fall through to HTTP_ERROR.
      }
    }
    if (ok) return decoded;
    throw ApiException.fromErrorBody(response.statusCode, decoded);
  }
}
