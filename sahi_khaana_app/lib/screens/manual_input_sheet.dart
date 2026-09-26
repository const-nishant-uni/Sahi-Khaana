import 'package:flutter/material.dart';
import 'package:sahi_khaana_app/api/api.dart';
import 'package:sahi_khaana_app/models/models.dart';
import 'package:sahi_khaana_app/theme/app_theme.dart';

class ManualInputSheet extends StatefulWidget {
  final SahiApi api;
  final String? initialCategory;
  final ValueChanged<ScanResult> onSuccess;

  const ManualInputSheet({
    super.key,
    required this.api,
    this.initialCategory,
    required this.onSuccess,
  });

  @override
  State<ManualInputSheet> createState() => _ManualInputSheetState();
}

class _ManualInputSheetState extends State<ManualInputSheet> {
  final TextEditingController _ingredientsController = TextEditingController();
  final TextEditingController _nutritionController = TextEditingController();
  bool _isSubmitting = false;

  @override
  void dispose() {
    _ingredientsController.dispose();
    _nutritionController.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    final text = _ingredientsController.text.trim();
    if (text.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Please enter ingredients text.')),
      );
      return;
    }

    setState(() => _isSubmitting = true);

    try {
      final req = AnalyzeRequest(
        ingredientsText: text,
        nutritionText: _nutritionController.text.trim().isNotEmpty
            ? _nutritionController.text.trim()
            : null,
        foodCategory: widget.initialCategory,
      );

      final result = await widget.api.analyze(req);
      if (!mounted) return;
      Navigator.of(context).pop();
      widget.onSuccess(result);
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() => _isSubmitting = false);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Error: ${e.message}')),
      );
    } catch (e) {
      if (!mounted) return;
      setState(() => _isSubmitting = false);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Failed to analyze: $e')),
      );
    }
  }

  void _fillSample() {
    _ingredientsController.text =
        'Wheat flour (65%), Edible Vegetable Oil (Palm), Sugar, Liquid Glucose, Milk Solids, Salt, Raising Agents (INS 500(ii), INS 503(ii)), Emulsifier (INS 322), Added Artificial Flavours (Vanilla)';
    _nutritionController.text =
        'Energy: 480 kcal, Protein: 7.2 g, Carbohydrate: 68 g, Total Sugars: 24 g, Added Sugars: 22 g, Total Fat: 20 g, Saturated Fat: 9.5 g, Sodium: 360 mg';
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: const BoxDecoration(
        color: AppTheme.surfaceCard,
        borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
      ),
      padding: EdgeInsets.only(
        left: 20,
        right: 20,
        top: 20,
        bottom: MediaQuery.of(context).viewInsets.bottom + 24,
      ),
      child: SingleChildScrollView(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                const Text(
                  'Direct Ingredient Check',
                  style: TextStyle(
                    fontSize: 18,
                    fontWeight: FontWeight.w700,
                    color: AppTheme.onSurface,
                  ),
                ),
                TextButton(
                  onPressed: _fillSample,
                  child: const Text('Fill Sample'),
                ),
              ],
            ),
            const SizedBox(height: 6),
            const Text(
              'Paste or type ingredient lists directly to test compliance.',
              style: TextStyle(fontSize: 13, color: AppTheme.onSurfaceVariant),
            ),
            const SizedBox(height: 16),
            const Text(
              'Ingredients List *',
              style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600),
            ),
            const SizedBox(height: 6),
            TextField(
              controller: _ingredientsController,
              maxLines: 4,
              decoration: InputDecoration(
                hintText: 'e.g. Wheat flour (72%), Sugar, Palm Oil, INS 621...',
                hintStyle: const TextStyle(fontSize: 13, color: AppTheme.outline),
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(8),
                  borderSide: const BorderSide(color: AppTheme.outlineVariant),
                ),
                focusedBorder: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(8),
                  borderSide: const BorderSide(color: AppTheme.primary, width: 1.5),
                ),
                filled: true,
                fillColor: AppTheme.surfaceContainerLow,
              ),
            ),
            const SizedBox(height: 14),
            const Text(
              'Nutrition Table Text (Optional)',
              style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600),
            ),
            const SizedBox(height: 6),
            TextField(
              controller: _nutritionController,
              maxLines: 2,
              decoration: InputDecoration(
                hintText: 'e.g. Energy 450 kcal, Sugar 20g, Sodium 400mg...',
                hintStyle: const TextStyle(fontSize: 13, color: AppTheme.outline),
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(8),
                  borderSide: const BorderSide(color: AppTheme.outlineVariant),
                ),
                focusedBorder: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(8),
                  borderSide: const BorderSide(color: AppTheme.primary, width: 1.5),
                ),
                filled: true,
                fillColor: AppTheme.surfaceContainerLow,
              ),
            ),
            const SizedBox(height: 20),
            ElevatedButton(
              onPressed: _isSubmitting ? null : _submit,
              child: _isSubmitting
                  ? const SizedBox(
                      width: 20,
                      height: 20,
                      child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                    )
                  : const Text('Analyze Ingredients'),
            ),
          ],
        ),
      ),
    );
  }
}
