import 'package:shared_preferences/shared_preferences.dart';
import 'package:uuid/uuid.dart';

import 'device_id_store.dart';

/// Persists the device id with `shared_preferences`, so it survives app restarts.
class SharedPrefsDeviceIdStore implements DeviceIdStore {
  SharedPrefsDeviceIdStore({this.key = defaultKey});

  static const defaultKey = 'sahi_khaana.device_id';

  final String key;
  Future<String>? _pending;

  @override
  Future<String> getOrCreate() => _pending ??= _load();

  Future<String> _load() async {
    final prefs = await SharedPreferences.getInstance();
    final stored = prefs.getString(key);
    if (stored != null && uuidPattern.hasMatch(stored)) return stored;

    // First run (or a corrupted value the backend would reject anyway): make a new one.
    final created = const Uuid().v4();
    await prefs.setString(key, created);
    return created;
  }
}
