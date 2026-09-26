import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import 'package:sahi_khaana_app/api/api.dart';
import 'package:sahi_khaana_app/screens/manual_input_sheet.dart';
import 'package:sahi_khaana_app/screens/results_screen.dart';
import 'package:sahi_khaana_app/theme/app_theme.dart';

class HomeScreen extends StatefulWidget {
  final SahiApi api;
  final VoidCallback onNavigateToScan;

  const HomeScreen({
    super.key,
    required this.api,
    required this.onNavigateToScan,
  });

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  final ImagePicker _picker = ImagePicker();
  bool _isLoading = false;

  Future<void> _pickAndScan(ImageSource source) async {
    try {
      final XFile? file = await _picker.pickImage(
        source: source,
        imageQuality: 90,
      );
      if (file == null) return;

      setState(() => _isLoading = true);

      final bytes = await file.readAsBytes();
      final result = await widget.api.scanBytes(
        bytes,
        filename: file.name,
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
      _showErrorDialog(e);
    } catch (e) {
      if (!mounted) return;
      setState(() => _isLoading = false);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Failed to process image: $e')),
      );
    }
  }

  void _showErrorDialog(ApiException e) {
    String title = 'Scan Error';
    String message = e.message;

    if (e.isRetakePhoto) {
      title = 'Please Retake Photo';
      message = 'The photo could not be read clearly. Ensure good lighting, avoid glare, and capture the full ingredient text.';
    } else if (e.code == ApiErrorCodes.fileTooLarge) {
      title = 'Image Too Large';
      message = 'Please select a smaller photo or compress it under 5MB.';
    } else if (e.isNetworkProblem) {
      title = 'Connection Problem';
      message = 'Could not reach backend at ${widget.api.client.config.baseUrl}. Make sure your backend server is running.';
    }

    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(title, style: const TextStyle(fontWeight: FontWeight.bold)),
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
    return Scaffold(
      appBar: AppBar(
        title: const Text('Food Label AI'),
        actions: [
          IconButton(
            icon: const Icon(Icons.info_outline, size: 22),
            onPressed: () {
              showAboutDialog(
                context: context,
                applicationName: 'Food Label AI',
                applicationVersion: '1.0.0',
                children: const [
                  Text(
                    'Independent food label intelligence decoding ingredients, FSSAI regulatory compliance, and nutritional parameters.',
                  ),
                ],
              );
            },
          ),
        ],
      ),
      body: _isLoading
          ? const Center(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  CircularProgressIndicator(color: AppTheme.primary),
                  SizedBox(height: 16),
                  Text(
                    'Analyzing food label...',
                    style: TextStyle(
                      color: AppTheme.onSurfaceVariant,
                      fontSize: 15,
                    ),
                  ),
                ],
              ),
            )
          : SingleChildScrollView(
              padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 24),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // Badge tag
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                    decoration: BoxDecoration(
                      color: AppTheme.surfaceCard,
                      borderRadius: BorderRadius.circular(4),
                      border: Border.all(color: AppTheme.outlineVariant),
                    ),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Container(
                          width: 6,
                          height: 6,
                          decoration: const BoxDecoration(
                            color: AppTheme.primary,
                            shape: BoxShape.circle,
                          ),
                        ),
                        const SizedBox(width: 6),
                        const Text(
                          'INDEPENDENT FOOD INTELLIGENCE',
                          style: TextStyle(
                            fontSize: 10,
                            fontWeight: FontWeight.w700,
                            letterSpacing: 0.8,
                            color: AppTheme.onSurfaceVariant,
                          ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 16),

                  // Headline
                  const Text(
                    'Know what’s in\nyour food.',
                    style: TextStyle(
                      fontSize: 32,
                      fontWeight: FontWeight.w700,
                      height: 1.2,
                      letterSpacing: -0.8,
                      color: AppTheme.onSurface,
                    ),
                  ),
                  const SizedBox(height: 12),
                  const Text(
                    'Scan a food label to understand its ingredients, FSSAI findings and health factors.',
                    style: TextStyle(
                      fontSize: 15,
                      height: 1.5,
                      color: AppTheme.onSurfaceVariant,
                    ),
                  ),
                  const SizedBox(height: 32),

                  // Actions Cluster
                  ElevatedButton.icon(
                    onPressed: () => _pickAndScan(ImageSource.camera),
                    icon: const Icon(Icons.photo_camera, size: 20),
                    label: const Text('Scan with Camera'),
                  ),
                  const SizedBox(height: 10),
                  OutlinedButton.icon(
                    onPressed: () => _pickAndScan(ImageSource.gallery),
                    icon: const Icon(Icons.upload_file, size: 20, color: AppTheme.onSurfaceVariant),
                    label: const Text('Upload Image from Gallery'),
                  ),
                  const SizedBox(height: 10),
                  OutlinedButton.icon(
                    onPressed: _openManualInput,
                    icon: const Icon(Icons.edit_note, size: 20, color: AppTheme.onSurfaceVariant),
                    label: const Text('Type Ingredients (Direct Check)'),
                  ),
                  const SizedBox(height: 12),
                  const Center(
                    child: Text(
                      'Supports packaged foods, drinks, and dietary supplements',
                      style: TextStyle(
                        fontSize: 12,
                        color: AppTheme.outline,
                      ),
                    ),
                  ),
                  const SizedBox(height: 36),

                  // How it Works Section
                  const Divider(),
                  const SizedBox(height: 24),
                  const Text(
                    'HOW IT WORKS',
                    style: TextStyle(
                      fontSize: 11,
                      fontWeight: FontWeight.w700,
                      letterSpacing: 1.0,
                      color: AppTheme.onSurfaceVariant,
                    ),
                  ),
                  const SizedBox(height: 16),

                  _buildStep(
                    number: '01',
                    title: 'SCAN',
                    description: 'Snap the ingredient list on any package label',
                  ),
                  const SizedBox(height: 16),
                  _buildStep(
                    number: '02',
                    title: 'ANALYZE',
                    description: 'Instant automated check of regulatory & health factors',
                  ),
                  const SizedBox(height: 16),
                  _buildStep(
                    number: '03',
                    title: 'UNDERSTAND',
                    description: 'Clear, honest summary in under 5 seconds',
                    isLast: true,
                  ),
                  const SizedBox(height: 20),
                ],
              ),
            ),
    );
  }

  Widget _buildStep({
    required String number,
    required String title,
    required String description,
    bool isLast = false,
  }) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Container(
          width: 30,
          height: 30,
          decoration: BoxDecoration(
            color: AppTheme.surfaceCard,
            borderRadius: BorderRadius.circular(4),
            border: Border.all(color: AppTheme.outlineVariant),
          ),
          alignment: Alignment.center,
          child: Text(
            number,
            style: const TextStyle(
              fontSize: 11,
              fontWeight: FontWeight.w700,
              color: AppTheme.primary,
            ),
          ),
        ),
        const SizedBox(width: 14),
        Expanded(
          child: Container(
            padding: EdgeInsets.only(bottom: isLast ? 0 : 16),
            decoration: BoxDecoration(
              border: isLast
                  ? null
                  : const Border(
                      bottom: BorderSide(color: AppTheme.surfaceContainer),
                    ),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: const TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.w700,
                    letterSpacing: 0.2,
                    color: AppTheme.onSurface,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  description,
                  style: const TextStyle(
                    fontSize: 13,
                    color: AppTheme.onSurfaceVariant,
                  ),
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }
}
