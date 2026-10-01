import 'package:flutter/material.dart';
import 'package:sahi_khaana_app/api/api.dart';
import 'package:sahi_khaana_app/models/models.dart';
import 'package:sahi_khaana_app/screens/fssai_detail_screen.dart';
import 'package:sahi_khaana_app/screens/health_detail_screen.dart';
import 'package:sahi_khaana_app/theme/app_theme.dart';
import 'package:sahi_khaana_app/widgets/status_badge.dart';

class ResultsScreen extends StatefulWidget {
  final ScanResult scanResult;
  final SahiApi api;

  const ResultsScreen({
    super.key,
    required this.scanResult,
    required this.api,
  });

  @override
  State<ResultsScreen> createState() => _ResultsScreenState();
}

class _ResultsScreenState extends State<ResultsScreen> {
  Explanation? _explanation;
  bool _isLoadingExplanation = false;
  String? _explanationError;

  Future<void> _fetchExplanation() async {
    final id = widget.scanResult.scanId;

    setState(() {
      _isLoadingExplanation = true;
      _explanationError = null;
    });

    try {
      final exp = await widget.api.explanation(id);
      if (mounted) {
        setState(() {
          _explanation = exp;
          _isLoadingExplanation = false;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _explanationError = 'Could not load explanation: $e';
          _isLoadingExplanation = false;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final result = widget.scanResult;
    final fssai = result.fssaiResult;
    final health = result.healthResult;

    final score = health.score;
    final healthLabel = score >= 75
        ? 'Optimal'
        : score >= 50
            ? 'Moderate'
            : 'Caution';
    final healthColor = score >= 75
        ? AppTheme.passText
        : score >= 50
            ? AppTheme.secondary
            : AppTheme.flagText;

    final totalIngredients = result.ingredients.length;
    final reviewCount = fssai.findings.where((f) => f.status == FssaiStatus.review).length;
    final flagCount = fssai.findings.where((f) => f.status == FssaiStatus.flag).length;

    String fssaiHeadline;
    if (fssai.overallStatus == FssaiStatus.pass) {
      fssaiHeadline = 'No configured issues detected';
    } else if (fssai.overallStatus == FssaiStatus.flag) {
      fssaiHeadline = 'Regulatory flags detected';
    } else {
      fssaiHeadline = 'Ingredients need review';
    }

    final nutrition = result.nutrition;

    return Scaffold(
      appBar: AppBar(
        title: const Text('tatvatracer'),
        actions: [
          IconButton(
            icon: const Icon(Icons.share_outlined, size: 20),
            onPressed: () {
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(content: Text('Report ready to share.')),
              );
            },
          ),
        ],
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Scan Meta Row
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Row(
                  children: [
                    Text(
                      'SCAN-${result.scanId.length > 6 ? result.scanId.substring(0, 6).toUpperCase() : result.scanId.toUpperCase()}',
                      style: const TextStyle(
                        fontSize: 11,
                        fontWeight: FontWeight.w700,
                        letterSpacing: 1.0,
                        color: AppTheme.onSurfaceVariant,
                      ),
                    ),
                    const SizedBox(width: 8),
                    Container(
                      width: 4,
                      height: 4,
                      decoration: const BoxDecoration(
                        color: AppTheme.outlineVariant,
                        shape: BoxShape.circle,
                      ),
                    ),
                    const SizedBox(width: 8),
                    const Text(
                      'Product Analysis',
                      style: TextStyle(fontSize: 12, color: AppTheme.onSurfaceVariant),
                    ),
                  ],
                ),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                  decoration: BoxDecoration(
                    color: AppTheme.surfaceContainer,
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: const Row(
                    children: [
                      Icon(Icons.verified, size: 14, color: AppTheme.primary),
                      SizedBox(width: 4),
                      Text(
                        'Verified DB',
                        style: TextStyle(fontSize: 11, color: AppTheme.onSurfaceVariant),
                      ),
                    ],
                  ),
                ),
              ],
            ),
            const SizedBox(height: 20),

            // SECTION 1: FSSAI CHECK CARD
            const Text(
              'FSSAI CHECK',
              style: TextStyle(
                fontSize: 11,
                fontWeight: FontWeight.w700,
                letterSpacing: 1.0,
                color: AppTheme.onSurfaceVariant,
              ),
            ),
            const SizedBox(height: 8),
            InkWell(
              borderRadius: BorderRadius.circular(12),
              onTap: () {
                Navigator.of(context).push(
                  MaterialPageRoute(
                    builder: (_) => FssaiDetailScreen(scanResult: result),
                  ),
                );
              },
              child: Card(
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      StatusBadge(status: fssai.overallStatus),
                      const SizedBox(width: 14),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              fssaiHeadline,
                              style: const TextStyle(
                                fontSize: 16,
                                fontWeight: FontWeight.w700,
                                color: AppTheme.onSurface,
                              ),
                            ),
                            const SizedBox(height: 4),
                            Text(
                              '$totalIngredients ingredients checked • $reviewCount review • $flagCount flag',
                              style: const TextStyle(
                                fontSize: 13,
                                color: AppTheme.onSurfaceVariant,
                              ),
                            ),
                            const SizedBox(height: 6),
                            const Row(
                              children: [
                                Text(
                                  'View ingredient rules',
                                  style: TextStyle(
                                    fontSize: 12,
                                    fontWeight: FontWeight.w600,
                                    color: AppTheme.primary,
                                  ),
                                ),
                                Icon(Icons.chevron_right, size: 16, color: AppTheme.primary),
                              ],
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),
            const SizedBox(height: 24),

            // SECTION 2: HEALTH ASSESSMENT CARD
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                const Text(
                  'HEALTH ASSESSMENT',
                  style: TextStyle(
                    fontSize: 11,
                    fontWeight: FontWeight.w700,
                    letterSpacing: 1.0,
                    color: AppTheme.onSurfaceVariant,
                  ),
                ),
                Text(
                  !nutrition.isEmpty ? 'Standard 100g basis' : 'Ingredients basis',
                  style: const TextStyle(fontSize: 11, color: AppTheme.onSurfaceVariant),
                ),
              ],
            ),
            const SizedBox(height: 8),
            InkWell(
              borderRadius: BorderRadius.circular(12),
              onTap: () {
                Navigator.of(context).push(
                  MaterialPageRoute(
                    builder: (_) => HealthDetailScreen(scanResult: result),
                  ),
                );
              },
              child: Card(
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        crossAxisAlignment: CrossAxisAlignment.baseline,
                        textBaseline: TextBaseline.alphabetic,
                        children: [
                          Text(
                            '$score',
                            style: const TextStyle(
                              fontSize: 36,
                              fontWeight: FontWeight.w800,
                              letterSpacing: -1,
                              color: AppTheme.onSurface,
                            ),
                          ),
                          const SizedBox(width: 10),
                          Text(
                            healthLabel,
                            style: TextStyle(
                              fontSize: 18,
                              fontWeight: FontWeight.w700,
                              color: healthColor,
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 10),

                      // Safety gauge bar (Stitch 6px flat)
                      ClipRRect(
                        borderRadius: BorderRadius.circular(3),
                        child: Container(
                          height: 6,
                          width: double.infinity,
                          color: AppTheme.surfaceContainer,
                          child: FractionallySizedBox(
                            alignment: Alignment.centerLeft,
                            widthFactor: (score / 100).clamp(0.05, 1.0),
                            child: Container(color: healthColor),
                          ),
                        ),
                      ),
                      const SizedBox(height: 16),

                      // Nutritional Factor Highlights
                      if (!nutrition.isEmpty) ...[
                        _buildFactorRow(
                          icon: (nutrition.sugarG != null && nutrition.sugarG! > 15)
                              ? Icons.warning_amber_rounded
                              : Icons.check_circle_outline,
                          iconColor: (nutrition.sugarG != null && nutrition.sugarG! > 15)
                              ? AppTheme.secondary
                              : AppTheme.passText,
                          title: 'Sugars',
                          value: '${nutrition.sugarG ?? 0}g / 100g',
                        ),
                        const Divider(height: 12),
                        _buildFactorRow(
                          icon: (nutrition.sodiumMg != null && nutrition.sodiumMg! > 400)
                              ? Icons.warning_amber_rounded
                              : Icons.check_circle_outline,
                          iconColor: (nutrition.sodiumMg != null && nutrition.sodiumMg! > 400)
                              ? AppTheme.secondary
                              : AppTheme.passText,
                          title: 'Sodium',
                          value: '${nutrition.sodiumMg ?? 0}mg / 100g',
                        ),
                        const Divider(height: 12),
                        _buildFactorRow(
                          icon: Icons.check_circle_outline,
                          iconColor: AppTheme.passText,
                          title: 'Protein',
                          value: '${nutrition.proteinG ?? 0}g / 100g',
                        ),
                      ] else ...[
                        const Text(
                          'Nutrition panel not detected on packaging. Health assessment derived from ingredient composition.',
                          style: TextStyle(fontSize: 12, color: AppTheme.onSurfaceVariant),
                        ),
                      ],
                    ],
                  ),
                ),
              ),
            ),
            const SizedBox(height: 24),

            // SECTION 3: AI EXPLANATION
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        const Row(
                          children: [
                            Icon(Icons.auto_awesome, size: 18, color: AppTheme.primary),
                            SizedBox(width: 8),
                            Text(
                              'AI Regulatory Explanation',
                              style: TextStyle(
                                fontSize: 14,
                                fontWeight: FontWeight.w700,
                                color: AppTheme.onSurface,
                              ),
                            ),
                          ],
                        ),
                        if (_explanation == null && !_isLoadingExplanation)
                          TextButton(
                            onPressed: _fetchExplanation,
                            child: const Text('Generate'),
                          ),
                      ],
                    ),
                    if (_isLoadingExplanation) ...[
                      const SizedBox(height: 12),
                      const Row(
                        children: [
                          SizedBox(
                            width: 16,
                            height: 16,
                            child: CircularProgressIndicator(strokeWidth: 2, color: AppTheme.primary),
                          ),
                          SizedBox(width: 10),
                          Text('Generating plain-English regulatory summary...',
                              style: TextStyle(fontSize: 12, color: AppTheme.onSurfaceVariant)),
                        ],
                      ),
                    ] else if (_explanation != null) ...[
                      const SizedBox(height: 10),
                      Text(
                        _explanation!.text,
                        style: const TextStyle(
                          fontSize: 13,
                          height: 1.45,
                          color: AppTheme.onSurface,
                        ),
                      ),
                      const SizedBox(height: 6),
                      Text(
                        'Source: ${_explanation!.source.name.toUpperCase()}',
                        style: const TextStyle(
                          fontSize: 10,
                          fontWeight: FontWeight.w600,
                          color: AppTheme.outline,
                        ),
                      ),
                    ] else if (_explanationError != null) ...[
                      const SizedBox(height: 8),
                      Text(_explanationError!, style: const TextStyle(fontSize: 12, color: AppTheme.flagText)),
                    ] else ...[
                      const SizedBox(height: 6),
                      const Text(
                        'Plain-English breakdown of why ingredients received pass, review, or flag statuses.',
                        style: TextStyle(fontSize: 12, color: AppTheme.onSurfaceVariant),
                      ),
                    ],
                  ],
                ),
              ),
            ),
            const SizedBox(height: 24),

            // Action Buttons
            ElevatedButton.icon(
              onPressed: () {
                Navigator.of(context).push(
                  MaterialPageRoute(
                    builder: (_) => FssaiDetailScreen(scanResult: result),
                  ),
                );
              },
              icon: const Icon(Icons.fact_check_outlined, size: 18),
              label: const Text('View Full FSSAI Analysis'),
            ),
            const SizedBox(height: 10),
            OutlinedButton.icon(
              onPressed: () => Navigator.of(context).pop(),
              icon: const Icon(Icons.camera_alt_outlined, size: 18),
              label: const Text('Scan Another Product'),
            ),
            const SizedBox(height: 24),
          ],
        ),
      ),
    );
  }

  Widget _buildFactorRow({
    required IconData icon,
    required Color iconColor,
    required String title,
    required String value,
  }) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Row(
          children: [
            Icon(icon, size: 16, color: iconColor),
            const SizedBox(width: 8),
            Text(
              title,
              style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w500),
            ),
          ],
        ),
        Text(
          value,
          style: const TextStyle(
            fontSize: 13,
            fontWeight: FontWeight.w600,
            color: AppTheme.onSurface,
          ),
        ),
      ],
    );
  }
}
