import 'package:flutter_test/flutter_test.dart';
import 'package:sahi_khaana_app/main.dart';
import 'package:sahi_khaana_app/services/device_id_store.dart';
import 'helpers.dart';

void main() {
  testWidgets('App renders Home screen with Editorial branding and actions', (WidgetTester tester) async {
    final fake = fakeApi((request) async {
      return jsonResponse({'items': []});
    });

    final deviceIdStore = InMemoryDeviceIdStore('test-device-uuid');

    await tester.pumpWidget(
      SahiKhaanaApp(
        api: fake.api,
        deviceIdStore: deviceIdStore,
      ),
    );
    await tester.pumpAndSettle();

    // Verify key editorial elements from Stitch design appear
    expect(find.text('Food Label AI'), findsWidgets);
    expect(find.text('INDEPENDENT FOOD INTELLIGENCE'), findsOneWidget);
    expect(find.textContaining('Know what’s in'), findsOneWidget);
    expect(find.text('Scan with Camera'), findsOneWidget);
    expect(find.text('Upload Image from Gallery'), findsOneWidget);
    expect(find.text('HOW IT WORKS'), findsOneWidget);
    expect(find.text('01'), findsOneWidget);
    expect(find.text('02'), findsOneWidget);
    expect(find.text('03'), findsOneWidget);
  });
}
