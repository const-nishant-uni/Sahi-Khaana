import 'dart:io' show File;
import 'dart:typed_data';

import '../models/models.dart';
import '../models/json_helpers.dart';
import 'api_client.dart';
import 'api_exception.dart';

/// Typed access to every backend endpoint (see docs/API_CHANGES.md in the backend repo).
///
/// Every method either returns parsed models or throws [ApiException]; nothing else escapes.
/// The `X-Device-Id` header is added automatically.
class SahiApi {
  SahiApi(this._client);

  final ApiClient _client;

  /// `GET /health`: is the server up? Returns its version string.
  Future<String> health() async {
    final json = await _client.getJson('/health');
    return _parse(json, (j) => j['version'] as String);
  }

  /// `GET /categories`: the food categories for the dropdown.
  Future<List<FoodCategory>> categories() async {
    final json = await _client.getJson('/categories');
    return _parse(
      json,
      (j) => asObjectList(j['categories'], FoodCategory.fromJson),
    );
  }

  /// `POST /scan`: analyse a label photo (JPG, PNG or WEBP, at most 5 MB).
  ///
  /// [foodCategory] is a [FoodCategory.id]. With image_picker:
  /// `api.scanBytes(await xfile.readAsBytes(), filename: xfile.name)`.
  /// Throws e.g. [ApiErrorCodes.poorImage], [ApiErrorCodes.noIngredientsSection]
  /// (see [ApiException.isRetakePhoto]).
  Future<ScanResult> scanBytes(
    Uint8List bytes, {
    required String filename,
    String? foodCategory,
  }) async {
    final json = await _client.postMultipart(
      '/scan',
      fileField: 'image',
      fileBytes: bytes,
      filename: filename,
      fields: {
        if (foodCategory != null && foodCategory.isNotEmpty)
          'food_category': foodCategory,
      },
    );
    return _parse(json, ScanResult.fromJson);
  }

  /// Same as [scanBytes] for a file on disk (not available on web).
  Future<ScanResult> scanFile(String path, {String? foodCategory}) async {
    final bytes = await File(path).readAsBytes();
    final name = path.split(RegExp(r'[\\/]')).last;
    return scanBytes(bytes, filename: name, foodCategory: foodCategory);
  }

  /// `POST /analyze`: the same analysis from typed text (no photo; `ocr` is null).
  Future<ScanResult> analyze(AnalyzeRequest request) async {
    final json = await _client.postJson('/analyze', request.toJson());
    return _parse(json, ScanResult.fromJson);
  }

  /// `GET /scans`: this device's history, newest first.
  Future<ScanPage> listScans({int limit = 20, int offset = 0}) async {
    RangeError.checkValueInInterval(limit, 1, 100, 'limit');
    RangeError.checkNotNegative(offset, 'offset');
    final json = await _client.getJson(
      '/scans',
      query: {'limit': '$limit', 'offset': '$offset'},
    );
    return _parse(json, ScanPage.fromJson);
  }

  /// `GET /scans/{id}`: the full stored result. Throws [ApiErrorCodes.scanNotFound]
  /// for an unknown id or another device's id.
  Future<ScanResult> getScan(String scanId) async {
    final json = await _client.getJson('/scans/${Uri.encodeComponent(scanId)}');
    return _parse(json, ScanResult.fromJson);
  }

  /// `DELETE /scans/{id}`: removes the scan and its photo. Throws
  /// [ApiErrorCodes.scanNotFound] if it does not exist (so a second delete throws).
  Future<void> deleteScan(String scanId) =>
      _client.delete('/scans/${Uri.encodeComponent(scanId)}');

  /// `GET /scans/{id}/explanation`. The first call can take a few seconds (it may call an
  /// AI); later calls return the cached text.
  Future<Explanation> explanation(String scanId) async {
    final json = await _client.getJson(
      '/scans/${Uri.encodeComponent(scanId)}/explanation',
    );
    return _parse(json, Explanation.fromJson);
  }

  /// `GET /mock/scan`: a fixed, realistic sample result, for layout work without a photo.
  Future<ScanResult> mockScan() async {
    final json = await _client.getJson('/mock/scan');
    return _parse(json, ScanResult.fromJson);
  }

  void close() => _client.close();

  /// Runs [build] on a JSON object; a missing/mistyped field becomes BAD_RESPONSE.
  T _parse<T>(Object? json, T Function(Json json) build) {
    try {
      return build(json as Json);
    } on ApiException {
      rethrow;
    } catch (e) {
      throw ApiException.badResponse(e);
    }
  }
}
