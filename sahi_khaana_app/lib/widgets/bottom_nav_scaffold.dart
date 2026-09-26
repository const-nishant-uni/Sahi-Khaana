import 'package:flutter/material.dart';
import 'package:sahi_khaana_app/api/api.dart';
import 'package:sahi_khaana_app/screens/home_screen.dart';
import 'package:sahi_khaana_app/screens/scan_screen.dart';
import 'package:sahi_khaana_app/screens/history_screen.dart';
import 'package:sahi_khaana_app/services/device_id_store.dart';
import 'package:sahi_khaana_app/theme/app_theme.dart';

class BottomNavScaffold extends StatefulWidget {
  final SahiApi api;
  final DeviceIdStore deviceIdStore;

  const BottomNavScaffold({
    super.key,
    required this.api,
    required this.deviceIdStore,
  });

  @override
  State<BottomNavScaffold> createState() => _BottomNavScaffoldState();
}

class _BottomNavScaffoldState extends State<BottomNavScaffold> {
  int _currentIndex = 0;

  @override
  Widget build(BuildContext context) {
    final List<Widget> pages = [
      HomeScreen(
        api: widget.api,
        onNavigateToScan: () => setState(() => _currentIndex = 1),
      ),
      ScanScreen(api: widget.api),
      HistoryScreen(
        api: widget.api,
        onScanTap: () => setState(() => _currentIndex = 1),
      ),
    ];

    return Scaffold(
      body: IndexedStack(
        index: _currentIndex,
        children: pages,
      ),
      bottomNavigationBar: Container(
        decoration: const BoxDecoration(
          color: AppTheme.surface,
          border: Border(
            top: BorderSide(color: AppTheme.outlineVariant, width: 1),
          ),
        ),
        child: BottomNavigationBar(
          currentIndex: _currentIndex,
          onTap: (index) => setState(() => _currentIndex = index),
          backgroundColor: AppTheme.surface,
          selectedItemColor: AppTheme.primary,
          unselectedItemColor: AppTheme.onSurfaceVariant,
          selectedLabelStyle: const TextStyle(
            fontSize: 11,
            fontWeight: FontWeight.w700,
            letterSpacing: 0.4,
          ),
          unselectedLabelStyle: const TextStyle(
            fontSize: 11,
            fontWeight: FontWeight.w500,
          ),
          type: BottomNavigationBarType.fixed,
          elevation: 0,
          items: const [
            BottomNavigationBarItem(
              icon: Icon(Icons.home_outlined),
              activeIcon: Icon(Icons.home),
              label: 'Home',
            ),
            BottomNavigationBarItem(
              icon: Icon(Icons.document_scanner_outlined),
              activeIcon: Icon(Icons.document_scanner),
              label: 'Scan',
            ),
            BottomNavigationBarItem(
              icon: Icon(Icons.history_outlined),
              activeIcon: Icon(Icons.history),
              label: 'History',
            ),
          ],
        ),
      ),
    );
  }
}
