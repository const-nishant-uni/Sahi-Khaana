import 'dart:io' show Platform;

/// Where the backend is and how long to wait for it.
///
/// Override the address without touching code:
///   flutter run --dart-define=API_BASE_URL=http://192.168.1.20:8000/api/v1
/// (needed on a physical phone: use your computer's LAN IP, same Wi-Fi).
class ApiConfig {
  const ApiConfig({
    required this.baseUrl,
    this.requestTimeout = const Duration(seconds: 30),
    this.scanTimeout = const Duration(seconds: 60),
  });

  /// Uses `--dart-define=API_BASE_URL=...` if given, otherwise the emulator/desktop default.
  factory ApiConfig.fromEnvironment() => ApiConfig(
    baseUrl: resolveBaseUrl(
      override: const String.fromEnvironment('API_BASE_URL'),
      isAndroid: Platform.isAndroid,
    ),
  );

  /// Android emulator: `10.0.2.2` is how the emulator reaches the computer's `localhost`.
  static const androidEmulatorBaseUrl = 'http://10.0.2.2:8000/api/v1';

  /// iOS simulator, desktop, or `adb reverse tcp:8000 tcp:8000`.
  static const localBaseUrl = 'http://localhost:8000/api/v1';

  /// The address to use. [override] wins; a trailing slash is removed.
  static String resolveBaseUrl({
    String override = '',
    required bool isAndroid,
  }) {
    final url = override.trim().isNotEmpty
        ? override.trim()
        : (isAndroid ? androidEmulatorBaseUrl : localBaseUrl);
    return url.endsWith('/') ? url.substring(0, url.length - 1) : url;
  }

  /// Includes the `/api/v1` prefix, no trailing slash.
  final String baseUrl;

  /// For everything except uploading a photo. A first `/explanation` call can take a few
  /// seconds (it may call an AI), so keep this generous.
  final Duration requestTimeout;

  /// For `POST /scan` (upload + OCR takes about 2-4 s on the server).
  final Duration scanTimeout;

  /// `baseUrl` + [path] (which starts with '/') + optional query string.
  Uri uri(String path, [Map<String, String>? query]) {
    final base = Uri.parse('$baseUrl$path');
    return query == null || query.isEmpty
        ? base
        : base.replace(queryParameters: query);
  }
}
