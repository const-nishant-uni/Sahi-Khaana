import 'package:flutter/material.dart';
import 'package:sahi_khaana_app/models/models.dart';
import 'package:sahi_khaana_app/theme/app_theme.dart';

class HealthDetailScreen extends StatelessWidget {
  final ScanResult scanResult;

  const HealthDetailScreen({super.key, required this.scanResult});

  @override
  Widget build(BuildContext context) {
    final health = scanResult.healthResult;
    final nutrition = scanResult.nutrition;

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

    return Scaffold(
      appBar: AppBar(
        title: const Text('Health Assessment'),
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Title Header
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                const Text(
                  'Health Assessment',
                  style: TextStyle(
                    fontSize: 22,
                    fontWeight: FontWeight.w700,
                    letterSpacing: -0.5,
                    color: AppTheme.onSurface,
                  ),
                ),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                  decoration: BoxDecoration(
                    color: AppTheme.surfaceContainerHigh,
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: AppTheme.outlineVariant),
                  ),
                  child: Text(
                    health.dataCompleteness.name.toUpperCase(),
                    style: const TextStyle(
                      fontSize: 10,
                      fontWeight: FontWeight.w700,
                      letterSpacing: 0.6,
                      color: AppTheme.onSurfaceVariant,
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 6),
            const Text(
              'Nutrient distribution, additive safety checks, and ingredient taxonomy analysis.',
              style: TextStyle(fontSize: 13, color: AppTheme.onSurfaceVariant, height: 1.4),
            ),
            const SizedBox(height: 20),

            // Bento Score Card
            Card(
              child: Padding(
                padding: const EdgeInsets.all(18),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      'AGGREGATE INDEX',
                      style: TextStyle(
                        fontSize: 10,
                        fontWeight: FontWeight.w700,
                        letterSpacing: 1.0,
                        color: AppTheme.onSurfaceVariant,
                      ),
                    ),
                    const SizedBox(height: 8),
                    Row(
                      crossAxisAlignment: CrossAxisAlignment.baseline,
                      textBaseline: TextBaseline.alphabetic,
                      children: [
                        Text(
                          '$score',
                          style: const TextStyle(
                            fontSize: 48,
                            fontWeight: FontWeight.w800,
                            letterSpacing: -1.5,
                            color: AppTheme.onSurface,
                          ),
                        ),
                        const SizedBox(width: 12),
                        Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              healthLabel,
                              style: TextStyle(
                                fontSize: 18,
                                fontWeight: FontWeight.w700,
                                color: healthColor,
                              ),
                            ),
                            const Text(
                              'Scale 0 (Caution) to 100 (Optimal)',
                              style: TextStyle(fontSize: 12, color: AppTheme.onSurfaceVariant),
                            ),
                          ],
                        ),
                      ],
                    ),
                    const SizedBox(height: 16),

                    // Gauge
                    const Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Text(
                          'Purity & Threshold Gauge',
                          style: TextStyle(fontSize: 11, fontWeight: FontWeight.w600, color: AppTheme.onSurfaceVariant),
                        ),
                        Text(
                          '100g Baseline',
                          style: TextStyle(fontSize: 11, color: AppTheme.outline),
                        ),
                      ],
                    ),
                    const SizedBox(height: 6),
                    ClipRRect(
                      borderRadius: BorderRadius.circular(4),
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
                    const SizedBox(height: 6),
                    const Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Text('0 Caution', style: TextStyle(fontSize: 10, color: AppTheme.outline)),
                        Text('50 Fair', style: TextStyle(fontSize: 10, color: AppTheme.outline)),
                        Text('100 Optimal', style: TextStyle(fontSize: 10, color: AppTheme.outline)),
                      ],
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 20),

            // Health Factors Breakdown from backend
            if (health.factors.isNotEmpty) ...[
              const Text(
                'HEALTH FACTORS EVALUATED',
                style: TextStyle(
                  fontSize: 11,
                  fontWeight: FontWeight.w700,
                  letterSpacing: 1.0,
                  color: AppTheme.onSurfaceVariant,
                ),
              ),
              const SizedBox(height: 8),
              Card(
                child: Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                  child: Column(
                    children: health.factors.map((factor) {
                      final isWarning = factor.impact < 0;
                      return Padding(
                        padding: const EdgeInsets.symmetric(vertical: 8),
                        child: Row(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Icon(
                              isWarning ? Icons.warning_amber_rounded : Icons.check_circle_outline,
                              size: 18,
                              color: isWarning ? AppTheme.secondary : AppTheme.passText,
                            ),
                            const SizedBox(width: 10),
                            Expanded(
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(
                                    factor.label,
                                    style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600),
                                  ),
                                  const SizedBox(height: 2),
                                  Text(
                                    factor.detail,
                                    style: const TextStyle(fontSize: 12, color: AppTheme.onSurfaceVariant),
                                  ),
                                ],
                              ),
                            ),
                            Container(
                              padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                              decoration: BoxDecoration(
                                color: isWarning ? AppTheme.reviewBg : AppTheme.passBg,
                                borderRadius: BorderRadius.circular(4),
                              ),
                              child: Text(
                                '${factor.impact > 0 ? "+" : ""}${factor.impact.toStringAsFixed(0)}',
                                style: TextStyle(
                                  fontSize: 11,
                                  fontWeight: FontWeight.w700,
                                  color: isWarning ? AppTheme.secondary : AppTheme.passText,
                                ),
                              ),
                            ),
                          ],
                        ),
                      );
                    }).toList(),
                  ),
                ),
              ),
              const SizedBox(height: 20),
            ],

            // Nutrition Ledger Table (if present)
            if (!nutrition.isEmpty) ...[
              const Text(
                'NUTRITION LEDGER (PER 100G)',
                style: TextStyle(
                  fontSize: 11,
                  fontWeight: FontWeight.w700,
                  letterSpacing: 1.0,
                  color: AppTheme.onSurfaceVariant,
                ),
              ),
              const SizedBox(height: 8),

              Card(
                child: Column(
                  children: [
                    _buildLedgerRow('Energy', '${nutrition.energyKcal?.toStringAsFixed(1) ?? "-"} kcal', true),
                    const Divider(),
                    _buildLedgerRow('Sugar', '${nutrition.sugarG?.toStringAsFixed(1) ?? "-"} g', false),
                    const Divider(),
                    _buildLedgerRow('Sodium', '${nutrition.sodiumMg?.toStringAsFixed(1) ?? "-"} mg', false),
                    const Divider(),
                    _buildLedgerRow('Total Fat', '${nutrition.totalFatG?.toStringAsFixed(1) ?? "-"} g', false),
                    const Divider(),
                    _buildLedgerRow('Saturated Fat', '${nutrition.satFatG?.toStringAsFixed(1) ?? "-"} g', false),
                    const Divider(),
                    _buildLedgerRow('Trans Fat', '${nutrition.transFatG?.toStringAsFixed(1) ?? "-"} g', false),
                    const Divider(),
                    _buildLedgerRow('Protein', '${nutrition.proteinG?.toStringAsFixed(1) ?? "-"} g', false),
                    const Divider(),
                    _buildLedgerRow('Dietary Fiber', '${nutrition.fiberG?.toStringAsFixed(1) ?? "-"} g', false),
                  ],
                ),
              ),
            ] else ...[
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    children: [
                      const Icon(Icons.info_outline, size: 28, color: AppTheme.secondary),
                      const SizedBox(height: 10),
                      const Text(
                        'No Nutrition Table Extracted',
                        style: TextStyle(fontSize: 15, fontWeight: FontWeight.w700),
                      ),
                      const SizedBox(height: 6),
                      Text(
                        'The photo captured the ingredient manifest. To see detailed nutrient metrics, photograph the Nutrition Information table on the packaging.',
                        textAlign: TextAlign.center,
                        style: TextStyle(fontSize: 13, color: AppTheme.onSurfaceVariant, height: 1.4),
                      ),
                    ],
                  ),
                ),
              ),
            ],
            const SizedBox(height: 16),

            // Health Disclaimer from backend
            Text(
              health.disclaimer,
              style: const TextStyle(fontSize: 11, fontStyle: FontStyle.italic, color: AppTheme.outline),
            ),
            const SizedBox(height: 24),
          ],
        ),
      ),
    );
  }

  Widget _buildLedgerRow(String label, String value, bool isHeader) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(
            label,
            style: TextStyle(
              fontSize: 13,
              fontWeight: isHeader ? FontWeight.w700 : FontWeight.w500,
              color: AppTheme.onSurface,
            ),
          ),
          Text(
            value,
            style: const TextStyle(
              fontSize: 13,
              fontWeight: FontWeight.w700,
              color: AppTheme.onSurface,
            ),
          ),
        ],
      ),
    );
  }
}
