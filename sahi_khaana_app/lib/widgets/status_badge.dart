import 'package:flutter/material.dart';
import 'package:sahi_khaana_app/models/models.dart';
import 'package:sahi_khaana_app/theme/app_theme.dart';

class StatusBadge extends StatelessWidget {
  final FssaiStatus status;
  final String? labelOverride;
  final bool compact;

  const StatusBadge({
    super.key,
    required this.status,
    this.labelOverride,
    this.compact = false,
  });

  @override
  Widget build(BuildContext context) {
    Color bg;
    Color border;
    Color text;
    String label;
    IconData icon;

    switch (status) {
      case FssaiStatus.pass:
        bg = AppTheme.passBg;
        border = AppTheme.passBorder;
        text = AppTheme.passText;
        label = labelOverride ?? 'PASS';
        icon = Icons.check_circle_outline;
        break;
      case FssaiStatus.review:
        bg = AppTheme.reviewBg;
        border = AppTheme.reviewBorder;
        text = AppTheme.reviewText;
        label = labelOverride ?? 'REVIEW';
        icon = Icons.warning_amber_rounded;
        break;
      case FssaiStatus.flag:
        bg = AppTheme.flagBg;
        border = AppTheme.flagBorder;
        text = AppTheme.flagText;
        label = labelOverride ?? 'FLAG';
        icon = Icons.error_outline;
        break;
    }

    if (compact) {
      return Container(
        padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
        decoration: BoxDecoration(
          color: bg,
          borderRadius: BorderRadius.circular(4),
          border: Border.all(color: border, width: 1),
        ),
        child: Text(
          label,
          style: TextStyle(
            color: text,
            fontSize: 10,
            fontWeight: FontWeight.w700,
            letterSpacing: 0.5,
          ),
        ),
      );
    }

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: bg,
        borderRadius: BorderRadius.circular(6),
        border: Border.all(color: border, width: 1),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 14, color: text),
          const SizedBox(width: 4),
          Text(
            label,
            style: TextStyle(
              color: text,
              fontSize: 11,
              fontWeight: FontWeight.w700,
              letterSpacing: 0.5,
            ),
          ),
        ],
      ),
    );
  }
}
