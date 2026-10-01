import 'package:flutter/material.dart';
import 'package:sahi_khaana_app/api/api.dart';
import 'package:sahi_khaana_app/services/api_provider.dart';
import 'package:sahi_khaana_app/services/device_id_store.dart';
import 'package:sahi_khaana_app/services/shared_prefs_device_id_store.dart';
import 'package:sahi_khaana_app/theme/app_theme.dart';
import 'package:sahi_khaana_app/widgets/bottom_nav_scaffold.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  final deviceIdStore = SharedPrefsDeviceIdStore();
  final api = createSahiApi();

  runApp(SahiKhaanaApp(api: api, deviceIdStore: deviceIdStore));
}

class SahiKhaanaApp extends StatelessWidget {
  final SahiApi api;
  final DeviceIdStore deviceIdStore;

  const SahiKhaanaApp({
    super.key,
    required this.api,
    required this.deviceIdStore,
  });

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'tatvatracer',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.lightTheme,
      home: BottomNavScaffold(api: api, deviceIdStore: deviceIdStore),
    );
  }
}
