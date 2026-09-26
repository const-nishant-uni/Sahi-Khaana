import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import 'package:sahi_khaana_app/api/api.dart';
import 'package:sahi_khaana_app/models/models.dart';
import 'package:sahi_khaana_app/screens/manual_input_sheet.dart';
import 'package:sahi_khaana_app/screens/results_screen.dart';
import 'package:sahi_khaana_app/theme/app_theme.dart';

class ScanScreen extends StatefulWidget {
  final SahiApi api;

  const ScanScreen({super.key, required this.api});

  @override
  State<ScanScreen> createState() => _ScanScreenState();
}

class _ScanScreenState extends State<ScanScreen> {
  final ImagePicker _picker = ImagePicker();
  List<FoodCategory> _categories = [];
  FoodCategory? _selectedCategory;
  bool _isLoading = false;
  String _statusText = 'Analyzing label...';

  @override
  void initState() {
    super.initState();
    _loadCategories();
  }

  Future<void> _loadCategories() async {
    try {
      final cats = await widget.api.categories();
      if (mounted) {
        setState(() => _categories = cats);
      }
    } catch (_) {
      // Categories are optional helper in scanning
    }
  }

  Future<void> _pickAndScan(ImageSource source) async {
    try {
      final XFile? file = await _picker.pickImage(
        source: source,
        imageQuality: 92,
      );
      if (file == null) return;

      setState(() {
        _isLoading = true;
        _statusText = 'Preprocessing & OCR scanning...';
      });

      final bytes = await file.readAsBytes();
      final result = await widget.api.scanBytes(
        bytes,
        filename: file.name,
        foodCategory: _selectedCategory?.id,
      );

      if (!mounted) return;
      setState(() => _isLoading = false);

      Navigator.of(context).push(
        MaterialPageRoute(
          builder: (_) => ResultsScreen(
            scanResult: result,
            api: widget.api,
          ),
        ),
      );
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() => _isLoading = false);
      _handleApiError(e);
    } catch (e) {
      if (!mounted) return;
      setState(() => _isLoading = false);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Scan failed: $e')),
      );
    }
  }

  void _handleApiError(ApiException e) {
    String title = 'Scanning Issue';
    String message = e.message;

    if (e.isRetakePhoto) {
      title = 'Retake Photo';
      message = 'Could not detect readable ingredients text. Please keep the camera steady, avoid glare, and frame the full label.';
    } else if (e.isNetworkProblem) {
      title = 'Backend Offline';
      message = 'Cannot reach backend at ${widget.api.client.config.baseUrl}. Please verify your local server is running.';
    }

    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(title),
        content: Text(message),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(),
            child: const Text('OK'),
          ),
        ],
      ),
    );
  }

  void _openManualInput() {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => ManualInputSheet(
        api: widget.api,
        initialCategory: _selectedCategory?.id,
        onSuccess: (result) {
          Navigator.of(context).push(
            MaterialPageRoute(
              builder: (_) => ResultsScreen(
                scanResult: result,
                api: widget.api,
              ),
            ),
          );
        },
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    if (_isLoading) {
      return Scaffold(
        appBar: AppBar(title: const Text('Food Label AI')),
        body: Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const CircularProgressIndicator(color: AppTheme.primary),
              const SizedBox(height: 20),
              Text(
                _statusText,
                style: const TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.w600,
                  color: AppTheme.onSurface,
                ),
              ),
              const SizedBox(height: 6),
              const Text(
                'Checking FSSAI compliance & nutrition values',
                style: TextStyle(
                  fontSize: 13,
                  color: AppTheme.onSurfaceVariant,
                ),
              ),
            ],
          ),
        ),
      );
    }

    return Scaffold(
      appBar: AppBar(
        title: const Text('Scan Label'),
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
        child: Column(
          children: [
            // Category Dropdown if available
            if (_categories.isNotEmpty) ...[
              Container(
                margin: const EdgeInsets.only(bottom: 16),
                padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 2),
                decoration: BoxDecoration(
                  color: AppTheme.surfaceCard,
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: AppTheme.outlineVariant),
                ),
                child: DropdownButtonHideUnderline(
                  child: DropdownButton<FoodCategory>(
                    isExpanded: true,
                    hint: const Text(
                      'Select category (Optional)',
                      style: TextStyle(fontSize: 14, color: AppTheme.onSurfaceVariant),
                    ),
                    value: _selectedCategory,
                    items: [
                      const DropdownMenuItem<FoodCategory>(
                        value: null,
                        child: Text('Auto-detect category', style: TextStyle(fontSize: 14)),
                      ),
                      ..._categories.map((c) => DropdownMenuItem(
                            value: c,
                            child: Text(c.name, style: const TextStyle(fontSize: 14)),
                          )),
                    ],
                    onChanged: (cat) => setState(() => _selectedCategory = cat),
                  ),
                ),
              ),
            ],

            // Viewfinder Framing Canvas (Stitch 4/5 Aspect Ratio Box)
            AspectRatio(
              aspectRatio: 4 / 4.6,
              child: Container(
                decoration: BoxDecoration(
                  color: AppTheme.surfaceCard,
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(color: AppTheme.outlineVariant),
                ),
                child: Stack(
                  children: [
                    // Corner Hairline Guides
                    Positioned(
                      top: 14,
                      left: 14,
                      child: Container(
                        width: 22,
                        height: 22,
                        decoration: const BoxDecoration(
                          border: Border(
                            top: BorderSide(color: AppTheme.primary, width: 2.5),
                            left: BorderSide(color: AppTheme.primary, width: 2.5),
                          ),
                        ),
                      ),
                    ),
                    Positioned(
                      top: 14,
                      right: 14,
                      child: Container(
                        width: 22,
                        height: 22,
                        decoration: const BoxDecoration(
                          border: Border(
                            top: BorderSide(color: AppTheme.primary, width: 2.5),
                            right: BorderSide(color: AppTheme.primary, width: 2.5),
                          ),
                        ),
                      ),
                    ),
                    Positioned(
                      bottom: 14,
                      left: 14,
                      child: Container(
                        width: 22,
                        height: 22,
                        decoration: const BoxDecoration(
                          border: Border(
                            bottom: BorderSide(color: AppTheme.primary, width: 2.5),
                            left: BorderSide(color: AppTheme.primary, width: 2.5),
                          ),
                        ),
                      ),
                    ),
                    Positioned(
                      bottom: 14,
                      right: 14,
                      child: Container(
                        width: 22,
                        height: 22,
                        decoration: const BoxDecoration(
                          border: Border(
                            bottom: BorderSide(color: AppTheme.primary, width: 2.5),
                            right: BorderSide(color: AppTheme.primary, width: 2.5),
                          ),
                        ),
                      ),
                    ),

                    // Center subtle horizontal alignment hairline
                    Align(
                      alignment: Alignment.center,
                      child: Container(
                        height: 1,
                        margin: const EdgeInsets.symmetric(horizontal: 24),
                        color: AppTheme.outlineVariant.withValues(alpha: 0.7),
                      ),
                    ),

                    // Central Target Icon & Prompt
                    Center(
                      child: Column(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Container(
                            width: 60,
                            height: 60,
                            decoration: BoxDecoration(
                              color: AppTheme.surfaceContainerLow,
                              shape: BoxShape.circle,
                              border: Border.all(color: AppTheme.outlineVariant),
                            ),
                            child: const Icon(
                              Icons.document_scanner,
                              size: 28,
                              color: AppTheme.primary,
                            ),
                          ),
                          const SizedBox(height: 12),
                          const Text(
                            'Place ingredient label here',
                            style: TextStyle(
                              fontSize: 15,
                              fontWeight: FontWeight.w600,
                              color: AppTheme.onSurface,
                            ),
                          ),
                          const SizedBox(height: 4),
                          const Text(
                            'Hold phone parallel to packaging',
                            style: TextStyle(
                              fontSize: 12,
                              color: AppTheme.onSurfaceVariant,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 24),

            // Action Buttons
            ElevatedButton.icon(
              onPressed: () => _pickAndScan(ImageSource.camera),
              icon: const Icon(Icons.photo_camera, size: 20),
              label: const Text('Take Photo'),
            ),
            const SizedBox(height: 10),
            OutlinedButton.icon(
              onPressed: () => _pickAndScan(ImageSource.gallery),
              icon: const Icon(Icons.upload_file, size: 20, color: AppTheme.onSurfaceVariant),
              label: const Text('Upload Image from Gallery'),
            ),
            const SizedBox(height: 10),
            TextButton.icon(
              onPressed: _openManualInput,
              icon: const Icon(Icons.keyboard, size: 18, color: AppTheme.primary),
              label: const Text(
                'Type or Paste Ingredients',
                style: TextStyle(color: AppTheme.primary, fontWeight: FontWeight.w600),
              ),
            ),
            const SizedBox(height: 8),
            const Text(
              'Keep the text clear and avoid glare.',
              style: TextStyle(
                fontSize: 12,
                color: AppTheme.onSurfaceVariant,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
