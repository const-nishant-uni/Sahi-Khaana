import 'package:flutter/material.dart';
import 'package:sahi_khaana_app/models/models.dart';
import 'package:sahi_khaana_app/theme/app_theme.dart';
import 'package:sahi_khaana_app/widgets/status_badge.dart';

class FssaiDetailScreen extends StatelessWidget {
  final ScanResult scanResult;

  const FssaiDetailScreen({super.key, required this.scanResult});

  @override
  Widget build(BuildContext context) {
    final fssai = scanResult.fssaiResult;
    final ingredients = scanResult.ingredients;

    final passCount = fssai.summary.pass;
    final reviewCount = fssai.summary.review;
    final flagCount = fssai.summary.flag;

    final labelFindings = fssai.labelLevelFindings;

    return Scaffold(
      appBar: AppBar(
        title: const Text('FSSAI Check'),
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Header block
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                const Text(
                  'FSSAI Check',
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
                    '${ingredients.length} INGREDIENTS',
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
              'Compliance assessment based on Food Safety and Standards Authority of India (FSSAI) packaging norms.',
              style: TextStyle(fontSize: 13, color: AppTheme.onSurfaceVariant, height: 1.4),
            ),
            const SizedBox(height: 18),

            // Quick Status Legend Bar (Stitch 3-Column Bar)
            Container(
              padding: const EdgeInsets.all(6),
              decoration: BoxDecoration(
                color: AppTheme.surfaceContainerLow,
                borderRadius: BorderRadius.circular(8),
                border: Border.all(color: AppTheme.outlineVariant),
              ),
              child: Row(
                children: [
                  Expanded(
                    child: _buildLegendItem(
                      dotColor: AppTheme.primary,
                      text: '$passCount PASS',
                      textColor: AppTheme.primary,
                    ),
                  ),
                  const SizedBox(width: 6),
                  Expanded(
                    child: _buildLegendItem(
                      dotColor: AppTheme.secondary,
                      text: '$reviewCount REVIEW',
                      textColor: AppTheme.secondary,
                    ),
                  ),
                  const SizedBox(width: 6),
                  Expanded(
                    child: _buildLegendItem(
                      dotColor: AppTheme.flagText,
                      text: '$flagCount FLAG',
                      textColor: AppTheme.flagText,
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 20),

            // Label-Level Findings (if any)
            if (labelFindings.isNotEmpty) ...[
              const Text(
                'LABEL-LEVEL FINDINGS',
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
                  padding: const EdgeInsets.all(14),
                  child: Column(
                    children: labelFindings.map((finding) {
                      return Padding(
                        padding: const EdgeInsets.symmetric(vertical: 4),
                        child: Row(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            StatusBadge(status: finding.status, compact: true),
                            const SizedBox(width: 10),
                            Expanded(
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(
                                    finding.ruleId,
                                    style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600),
                                  ),
                                  const SizedBox(height: 2),
                                  Text(
                                    finding.reason,
                                    style: const TextStyle(fontSize: 12, color: AppTheme.onSurfaceVariant),
                                  ),
                                ],
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

            // Analyzed Ingredients List
            const Text(
              'ANALYZED INGREDIENTS',
              style: TextStyle(
                fontSize: 11,
                fontWeight: FontWeight.w700,
                letterSpacing: 1.0,
                color: AppTheme.onSurfaceVariant,
              ),
            ),
            const SizedBox(height: 8),

            Card(
              child: ListView.separated(
                shrinkWrap: true,
                physics: const NeverScrollableScrollPhysics(),
                itemCount: ingredients.length,
                separatorBuilder: (context, i) => const Divider(),
                itemBuilder: (context, index) {
                  final ing = ingredients[index];
                  final findings = fssai.findingsFor(ing.id);

                  FssaiStatus status = FssaiStatus.pass;
                  String? message;
                  if (findings.any((f) => f.status == FssaiStatus.flag)) {
                    status = FssaiStatus.flag;
                    message = findings.firstWhere((f) => f.status == FssaiStatus.flag).reason;
                  } else if (findings.any((f) => f.status == FssaiStatus.review)) {
                    status = FssaiStatus.review;
                    message = findings.firstWhere((f) => f.status == FssaiStatus.review).reason;
                  } else {
                    status = FssaiStatus.pass;
                    message = 'Standard recognized ingredient';
                  }

                  return Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        _buildStatusIcon(status),
                        const SizedBox(width: 12),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Row(
                                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                                children: [
                                  Expanded(
                                    child: Text(
                                      ing.displayName,
                                      style: const TextStyle(
                                        fontSize: 14,
                                        fontWeight: FontWeight.w600,
                                        color: AppTheme.onSurface,
                                      ),
                                    ),
                                  ),
                                  StatusBadge(status: status, compact: true),
                                ],
                              ),
                              if (ing.percentage != null) ...[
                                const SizedBox(height: 2),
                                Text(
                                  'Declared amount: ${ing.percentage}%',
                                  style: const TextStyle(fontSize: 11, color: AppTheme.outline),
                                ),
                              ],
                              const SizedBox(height: 3),
                              Text(
                                message,
                                style: const TextStyle(
                                  fontSize: 12,
                                  color: AppTheme.onSurfaceVariant,
                                ),
                              ),
                            ],
                          ),
                        ),
                      ],
                    ),
                  );
                },
              ),
            ),
            const SizedBox(height: 20),

            // Legal & Methodology Note (Stitch design expandable)
            Container(
              padding: const EdgeInsets.all(14),
              decoration: BoxDecoration(
                color: AppTheme.surfaceContainerLow,
                borderRadius: BorderRadius.circular(8),
                border: Border.all(color: AppTheme.outlineVariant),
              ),
              child: const Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'REGULATORY METHODOLOGY',
                    style: TextStyle(
                      fontSize: 11,
                      fontWeight: FontWeight.w700,
                      letterSpacing: 0.8,
                      color: AppTheme.onSurfaceVariant,
                    ),
                  ),
                  SizedBox(height: 6),
                  Text(
                    'Evaluated against Food Safety and Standards (Packaging and Labelling) Regulations. "Review" flags denote permitted additives with statutory maximum usage limits or advisory labeling requirements.',
                    style: TextStyle(fontSize: 12, height: 1.4, color: AppTheme.onSurfaceVariant),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 24),
          ],
        ),
      ),
    );
  }

  Widget _buildLegendItem({
    required Color dotColor,
    required String text,
    required Color textColor,
  }) {
    return Container(
      padding: const EdgeInsets.symmetric(vertical: 6, horizontal: 8),
      decoration: BoxDecoration(
        color: AppTheme.surfaceCard,
        borderRadius: BorderRadius.circular(4),
        border: Border.all(color: AppTheme.outlineVariant),
      ),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Container(
            width: 6,
            height: 6,
            decoration: BoxDecoration(color: dotColor, shape: BoxShape.circle),
          ),
          const SizedBox(width: 6),
          Text(
            text,
            style: TextStyle(
              fontSize: 11,
              fontWeight: FontWeight.w700,
              letterSpacing: 0.4,
              color: textColor,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildStatusIcon(FssaiStatus status) {
    Color bg;
    Color border;
    Color iconColor;
    IconData icon;

    switch (status) {
      case FssaiStatus.pass:
        bg = AppTheme.passBg;
        border = AppTheme.passBorder;
        iconColor = AppTheme.passText;
        icon = Icons.check;
        break;
      case FssaiStatus.review:
        bg = AppTheme.reviewBg;
        border = AppTheme.reviewBorder;
        iconColor = AppTheme.reviewText;
        icon = Icons.warning_amber_rounded;
        break;
      case FssaiStatus.flag:
        bg = AppTheme.flagBg;
        border = AppTheme.flagBorder;
        iconColor = AppTheme.flagText;
        icon = Icons.close;
        break;
    }

    return Container(
      width: 24,
      height: 24,
      decoration: BoxDecoration(
        color: bg,
        shape: BoxShape.circle,
        border: Border.all(color: border),
      ),
      alignment: Alignment.center,
      child: Icon(icon, size: 14, color: iconColor),
    );
  }
}
