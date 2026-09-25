import '../api/api.dart';
import 'shared_prefs_device_id_store.dart';

/// The app's ready-to-use API: address from `--dart-define=API_BASE_URL` (or the emulator
/// default) and a device id that persists across restarts. Create it ONCE at startup and share it:
///
///   final api = createSahiApi();
///   final categories = await api.categories();
SahiApi createSahiApi({ApiConfig? config}) => SahiApi(
  ApiClient(
    config: config ?? ApiConfig.fromEnvironment(),
    deviceIdStore: SharedPrefsDeviceIdStore(),
  ),
);
