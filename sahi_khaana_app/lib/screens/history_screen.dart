import 'package:flutter/material.dart';
import 'package:sahi_khaana_app/api/api.dart';
import 'package:sahi_khaana_app/models/models.dart';
import 'package:sahi_khaana_app/screens/results_screen.dart';
import 'package:sahi_khaana_app/theme/app_theme.dart';
import 'package:sahi_khaana_app/widgets/status_badge.dart';

class HistoryScreen extends StatefulWidget {
  final SahiApi api;
  final VoidCallback onScanTap;

  const HistoryScreen({
    super.key,
    required this.api,
    required this.onScanTap,
  });

  @override
  State<HistoryScreen> createState() => _HistoryScreenState();
}

class _HistoryScreenState extends State<HistoryScreen> {
  List<ScanSummary> _items = [];
  bool _isLoading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _loadHistory();
  }

  Future<void> _loadHistory() async {
    setState(() {
      _isLoading = true;
      _error = null;
    });

    try {
      final page = await widget.api.listScans(limit: 50, offset: 0);
      if (mounted) {
        setState(() {
          _items = page.items;
          _isLoading = false;
        });
      }
    } on ApiException catch (e) {
      if (mounted) {
        setState(() {
          _error = e.message;
          _isLoading = false;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _error = 'Failed to load history: $e';
          _isLoading = false;
        });
      }
    }
  }

  Future<void> _deleteItem(String id) async {
    try {
      await widget.api.deleteScan(id);
      setState(() {
        _items.removeWhere((item) => item.scanId == id);
      });
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Scan removed from history.')),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Delete failed: $e')),
        );
      }
    }
  }

  Future<void> _openItem(String id) async {
    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (_) => const Center(
        child: CircularProgressIndicator(color: AppTheme.primary),
      ),
    );

    try {
      final scan = await widget.api.getScan(id);
      if (!mounted) return;
      Navigator.of(context).pop(); // dismiss loading

      Navigator.of(context).push(
        MaterialPageRoute(
          builder: (_) => ResultsScreen(
            scanResult: scan,
            api: widget.api,
          ),
        ),
      );
    } catch (e) {
      if (!mounted) return;
      Navigator.of(context).pop(); // dismiss loading
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Could not open scan: $e')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Scan History'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh, size: 20),
            onPressed: _loadHistory,
          ),
        ],
      ),
      body: _buildBody(),
    );
  }

  Widget _buildBody() {
    if (_isLoading) {
      return const Center(child: CircularProgressIndicator(color: AppTheme.primary));
    }

    if (_error != null) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.wifi_off, size: 36, color: AppTheme.outline),
              const SizedBox(height: 12),
              const Text(
                'Could not load history',
                style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
              ),
              const SizedBox(height: 6),
              Text(
                _error!,
                textAlign: TextAlign.center,
                style: const TextStyle(fontSize: 13, color: AppTheme.onSurfaceVariant),
              ),
              const SizedBox(height: 16),
              ElevatedButton(
                onPressed: _loadHistory,
                child: const Text('Retry'),
              ),
            ],
          ),
        ),
      );
    }

    if (_items.isEmpty) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(32),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Container(
                width: 64,
                height: 64,
                decoration: BoxDecoration(
                  color: AppTheme.surfaceContainerLow,
                  shape: BoxShape.circle,
                  border: Border.all(color: AppTheme.outlineVariant),
                ),
                child: const Icon(Icons.history, size: 32, color: AppTheme.outline),
              ),
              const SizedBox(height: 16),
              const Text(
                'No Scans Yet',
                style: TextStyle(
                  fontSize: 18,
                  fontWeight: FontWeight.w700,
                  color: AppTheme.onSurface,
                ),
              ),
              const SizedBox(height: 8),
              const Text(
                'Scans you perform are stored anonymously and linked to this device.',
                textAlign: TextAlign.center,
                style: TextStyle(fontSize: 13, color: AppTheme.onSurfaceVariant, height: 1.4),
              ),
              const SizedBox(height: 24),
              ElevatedButton.icon(
                onPressed: widget.onScanTap,
                icon: const Icon(Icons.photo_camera, size: 18),
                label: const Text('Scan First Product'),
              ),
            ],
          ),
        ),
      );
    }

    return RefreshIndicator(
      onRefresh: _loadHistory,
      color: AppTheme.primary,
      child: ListView.separated(
        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
        itemCount: _items.length,
        separatorBuilder: (context, i) => const SizedBox(height: 10),
        itemBuilder: (context, index) {
          final item = _items[index];
          final dateStr =
              '${item.createdAt.day}/${item.createdAt.month}/${item.createdAt.year} ${item.createdAt.hour.toString().padLeft(2, '0')}:${item.createdAt.minute.toString().padLeft(2, '0')}';

          return Dismissible(
            key: Key(item.scanId),
            direction: DismissDirection.endToStart,
            background: Container(
              alignment: Alignment.centerRight,
              padding: const EdgeInsets.only(right: 20),
              decoration: BoxDecoration(
                color: AppTheme.flagBg,
                borderRadius: BorderRadius.circular(12),
              ),
              child: const Icon(Icons.delete_outline, color: AppTheme.flagText),
            ),
            confirmDismiss: (dir) async {
              return await showDialog<bool>(
                context: context,
                builder: (ctx) => AlertDialog(
                  title: const Text('Delete scan?'),
                  content: const Text('This scan will be permanently removed from your history.'),
                  actions: [
                    TextButton(onPressed: () => Navigator.of(ctx).pop(false), child: const Text('Cancel')),
                    TextButton(
                      onPressed: () => Navigator.of(ctx).pop(true),
                      child: const Text('Delete', style: TextStyle(color: AppTheme.flagText)),
                    ),
                  ],
                ),
              );
            },
            onDismissed: (_) => _deleteItem(item.scanId),
            child: InkWell(
              borderRadius: BorderRadius.circular(12),
              onTap: () => _openItem(item.scanId),
              child: Card(
                child: Padding(
                  padding: const EdgeInsets.all(14),
                  child: Row(
                    children: [
                      StatusBadge(status: item.overallStatus),
                      const SizedBox(width: 14),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              item.foodCategory ?? 'Food Product',
                              style: const TextStyle(
                                fontSize: 14,
                                fontWeight: FontWeight.w700,
                                color: AppTheme.onSurface,
                              ),
                            ),
                            const SizedBox(height: 3),
                            Text(
                              '$dateStr • ${item.ingredientCount} ingredients',
                              style: const TextStyle(
                                fontSize: 12,
                                color: AppTheme.onSurfaceVariant,
                              ),
                            ),
                          ],
                        ),
                      ),
                      const Icon(Icons.chevron_right, size: 18, color: AppTheme.outline),
                    ],
                  ),
                ),
              ),
            ),
          );
        },
      ),
    );
  }
}
