import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:sahi_khaana_app/services/device_id_store.dart';
import 'package:sahi_khaana_app/services/shared_prefs_device_id_store.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  group('SharedPrefsDeviceIdStore', () {
    setUp(() => SharedPreferences.setMockInitialValues({}));

    test('creates a UUID on first use and stores it', () async {
      final id = await SharedPrefsDeviceIdStore().getOrCreate();
      expect(uuidPattern.hasMatch(id), isTrue);
      expect((await SharedPreferences.getInstance()).getString(SharedPrefsDeviceIdStore.defaultKey), id);
    });

    test('the same id comes back after an app restart (a new store instance)', () async {
      final first = await SharedPrefsDeviceIdStore().getOrCreate();
      final second = await SharedPrefsDeviceIdStore().getOrCreate();
      expect(second, first);
    });

    test('an existing stored id is used, not replaced', () async {
      SharedPreferences.setMockInitialValues({
        SharedPrefsDeviceIdStore.defaultKey: '3f0c2c5e-8a4b-4c6f-9d1e-2b7a5e9c1d34',
      });
      expect(await SharedPrefsDeviceIdStore().getOrCreate(), '3f0c2c5e-8a4b-4c6f-9d1e-2b7a5e9c1d34');
    });

    test('a corrupted stored value is replaced with a valid UUID', () async {
      SharedPreferences.setMockInitialValues({SharedPrefsDeviceIdStore.defaultKey: 'not-a-uuid'});
      final id = await SharedPrefsDeviceIdStore().getOrCreate();
      expect(uuidPattern.hasMatch(id), isTrue);
      expect(await SharedPrefsDeviceIdStore().getOrCreate(), id); // and it stuck
    });

    test('concurrent first calls still produce ONE id', () async {
      final store = SharedPrefsDeviceIdStore();
      final ids = await Future.wait([store.getOrCreate(), store.getOrCreate(), store.getOrCreate()]);
      expect(ids.toSet(), hasLength(1));
    });

    test('different keys are independent', () async {
      final a = await SharedPrefsDeviceIdStore(key: 'a').getOrCreate();
      final b = await SharedPrefsDeviceIdStore(key: 'b').getOrCreate();
      expect(a, isNot(b));
    });
  });

  group('InMemoryDeviceIdStore', () {
    test('creates once, then repeats', () async {
      final store = InMemoryDeviceIdStore();
      expect(await store.getOrCreate(), await store.getOrCreate());
    });

    test('uses a given id', () async {
      expect(await InMemoryDeviceIdStore('abc').getOrCreate(), 'abc');
    });
  });

  test('uuidPattern accepts UUIDs and rejects junk', () {
    expect(uuidPattern.hasMatch('3f0c2c5e-8a4b-4c6f-9d1e-2b7a5e9c1d34'), isTrue);
    expect(uuidPattern.hasMatch('3F0C2C5E-8A4B-4C6F-9D1E-2B7A5E9C1D34'), isTrue);
    expect(uuidPattern.hasMatch('3f0c2c5e8a4b4c6f9d1e2b7a5e9c1d34'), isFalse);
    expect(uuidPattern.hasMatch(''), isFalse);
  });
}
