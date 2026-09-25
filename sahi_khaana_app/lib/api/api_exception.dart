/// Error `code` values. The first group comes from the backend
/// (`{"error": {"code", "message"}}`); the last three are produced by this client.
abstract final class ApiErrorCodes {
  // --- from the backend
  static const missingDeviceId = 'MISSING_DEVICE_ID'; // 400
  static const invalidDeviceId = 'INVALID_DEVICE_ID'; // 400
  static const invalidFile = 'INVALID_FILE'; // 400
  static const invalidCategory = 'INVALID_CATEGORY'; // 400
  static const scanNotFound = 'SCAN_NOT_FOUND'; // 404
  static const notFound = 'NOT_FOUND'; // 404 (unknown URL)
  static const methodNotAllowed = 'METHOD_NOT_ALLOWED'; // 405
  static const fileTooLarge = 'FILE_TOO_LARGE'; // 413
  static const poorImage = 'POOR_IMAGE'; // 422
  static const noTextFound = 'NO_TEXT_FOUND'; // 422
  static const noIngredientsSection = 'NO_INGREDIENTS_SECTION'; // 422
  static const validationError = 'VALIDATION_ERROR'; // 422
  static const httpError = 'HTTP_ERROR'; // any other HTTP error
  static const internalError = 'INTERNAL_ERROR'; // 500

  // --- produced by this client (no HTTP response was usable)
  static const networkError = 'NETWORK_ERROR'; // could not reach the server
  static const timeout = 'TIMEOUT'; // no answer in time
  static const badResponse = 'BAD_RESPONSE'; // 2xx but not the JSON we expected
}

/// Every failed API call throws this. Switch on [code], not on [message].
class ApiException implements Exception {
  const ApiException({
    required this.code,
    required this.message,
    this.statusCode,
  });

  /// From `{"error": {"code", "message"}}`, or a client-side code (network, timeout...).
  factory ApiException.fromErrorBody(int statusCode, Object? decoded) {
    if (decoded is Map && decoded['error'] is Map) {
      final error = decoded['error'] as Map;
      final code = error['code'];
      final message = error['message'];
      if (code is String) {
        return ApiException(
          code: code,
          message: message is String ? message : code,
          statusCode: statusCode,
        );
      }
    }
    return ApiException(
      code: ApiErrorCodes.httpError,
      message: 'HTTP $statusCode',
      statusCode: statusCode,
    );
  }

  factory ApiException.network(Object cause) => ApiException(
    code: ApiErrorCodes.networkError,
    message: 'Could not reach the server: $cause',
  );

  factory ApiException.timeout(Duration after) => ApiException(
    code: ApiErrorCodes.timeout,
    message: 'The server did not answer within ${after.inSeconds} s.',
  );

  factory ApiException.badResponse(Object cause) => ApiException(
    code: ApiErrorCodes.badResponse,
    message: 'Unexpected response from the server: $cause',
  );

  /// One of [ApiErrorCodes].
  final String code;

  /// For logs and debugging. Show your own wording per [code] in the UI.
  final String message;

  /// Null for client-side errors (network, timeout, bad response).
  final int? statusCode;

  bool get isNetworkProblem =>
      code == ApiErrorCodes.networkError || code == ApiErrorCodes.timeout;

  /// The photo could not be used: ask the user to retake it / photograph the ingredients.
  bool get isRetakePhoto =>
      code == ApiErrorCodes.poorImage ||
      code == ApiErrorCodes.noTextFound ||
      code == ApiErrorCodes.noIngredientsSection;

  bool get isScanNotFound => code == ApiErrorCodes.scanNotFound;

  @override
  String toString() => 'ApiException($code${statusCode == null ? '' : ', $statusCode'}): $message';
}
