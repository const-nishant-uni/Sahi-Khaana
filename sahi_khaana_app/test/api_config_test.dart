import 'package:flutter_test/flutter_test.dart';
import 'package:sahi_khaana_app/api/api.dart';

void main() {
  group('resolveBaseUrl', () {
    test('Android default is the emulator address', () {
      expect(ApiConfig.resolveBaseUrl(isAndroid: true), 'http://10.0.2.2:8000/api/v1');
    });

    test('other platforms default to localhost', () {
      expect(ApiConfig.resolveBaseUrl(isAndroid: false), 'http://localhost:8000/api/v1');
    });

    test('an override wins on every platform (--dart-define=API_BASE_URL=...)', () {
      for (final android in [true, false]) {
        expect(
          ApiConfig.resolveBaseUrl(override: 'http://192.168.1.20:8000/api/v1', isAndroid: android),
          'http://192.168.1.20:8000/api/v1',
        );
      }
    });

    test('blank override is ignored; trailing slash and spaces are trimmed', () {
      expect(ApiConfig.resolveBaseUrl(override: '   ', isAndroid: true), ApiConfig.androidEmulatorBaseUrl);
      expect(ApiConfig.resolveBaseUrl(override: ' http://h/api/v1/ ', isAndroid: false), 'http://h/api/v1');
    });
  });

  group('ApiConfig', () {
    const config = ApiConfig(baseUrl: 'http://h:8000/api/v1');

    test('uri() adds the path and query', () {
      expect(config.uri('/health').toString(), 'http://h:8000/api/v1/health');
      expect(config.uri('/scans', {'limit': '5'}).toString(), 'http://h:8000/api/v1/scans?limit=5');
      expect(config.uri('/scans', {}).toString(), 'http://h:8000/api/v1/scans');
    });

    test('timeouts are generous by default', () {
      expect(config.requestTimeout, const Duration(seconds: 30));
      expect(config.scanTimeout, const Duration(seconds: 60));
    });

    test('fromEnvironment gives a usable URL on the test host', () {
      final url = ApiConfig.fromEnvironment().baseUrl;
      expect(url, endsWith('/api/v1'));
      expect(Uri.parse(url).hasAuthority, isTrue);
    });
  });
}
