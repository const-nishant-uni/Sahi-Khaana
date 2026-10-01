import 'package:flutter/material.dart';

/// Editorial Food Science Design Theme extracted directly from the Stitch design system.
class AppTheme {
  AppTheme._();

  // Core brand palette
  static const Color primary = Color(0xFF1E5132); // Forest Green
  static const Color primaryContainer = Color(0xFF1E5132);
  static const Color onPrimary = Color(0xFFFFFFFF);
  static const Color primaryFixed = Color(0xFFB8F0C5);

  static const Color background = Color(0xFFFCF9F8); // Warm Paper Canvas
  static const Color surface = Color(0xFFFCF9F8);
  static const Color surfaceCard = Color(0xFFFFFFFF);
  static const Color surfaceContainerLow = Color(0xFFF6F3F2);
  static const Color surfaceContainer = Color(0xFFF0EDED);
  static const Color surfaceContainerHigh = Color(0xFFEAE7E7);

  static const Color onSurface = Color(0xFF1C1B1B); // Deep Charcoal
  static const Color onSurfaceVariant = Color(0xFF414942); // Dried Lichen Gray
  static const Color outline = Color(0xFF717971);
  static const Color outlineVariant = Color(0xFFE5E2E1); // Structural Hairline

  // Semantic Status Tiers
  static const Color secondary = Color(0xFF9B4500); // Amber / Moderate Risk

  // Pass Tier (Verified)
  static const Color passBg = Color(0xFFF0FDF4);
  static const Color passBorder = Color(0xFFBBF7D0);
  static const Color passText = Color(0xFF1E5132);

  // Review Tier (Needs Review)
  static const Color reviewBg = Color(0xFFFFFBEB);
  static const Color reviewBorder = Color(0xFFFDE68A);
  static const Color reviewText = Color(0xFFB45309);

  // Flag Tier (High Risk / Contraindication)
  static const Color flagBg = Color(0xFFFEF2F2);
  static const Color flagBorder = Color(0xFFFECACA);
  static const Color flagText = Color(0xFFBA1A1A);

  static ThemeData get lightTheme {
    return ThemeData(
      useMaterial3: true,
      scaffoldBackgroundColor: background,
      colorScheme: const ColorScheme(
        brightness: Brightness.light,
        primary: primary,
        onPrimary: onPrimary,
        primaryContainer: primaryContainer,
        onPrimaryContainer: Color(0xFF8DC39B),
        secondary: secondary,
        onSecondary: Color(0xFFFFFFFF),
        error: flagText,
        onError: Color(0xFFFFFFFF),
        surface: surface,
        onSurface: onSurface,
        onSurfaceVariant: onSurfaceVariant,
        outline: outline,
        outlineVariant: outlineVariant,
      ),
      appBarTheme: const AppBarTheme(
        backgroundColor: surface,
        foregroundColor: onSurface,
        elevation: 0,
        scrolledUnderElevation: 0,
        centerTitle: true,
        titleTextStyle: TextStyle(
          color: onSurface,
          fontSize: 18,
          fontWeight: FontWeight.w700,
          letterSpacing: -0.2,
        ),
      ),
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: primaryContainer,
          foregroundColor: onPrimary,
          minimumSize: const Size.fromHeight(48),
          elevation: 0,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(8),
          ),
          textStyle: const TextStyle(
            fontSize: 15,
            fontWeight: FontWeight.w600,
            letterSpacing: -0.1,
          ),
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          foregroundColor: onSurface,
          minimumSize: const Size.fromHeight(48),
          elevation: 0,
          side: const BorderSide(color: outlineVariant, width: 1),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(8),
          ),
          textStyle: const TextStyle(
            fontSize: 15,
            fontWeight: FontWeight.w500,
          ),
        ),
      ),
      cardTheme: CardThemeData(
        color: surfaceCard,
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(12),
          side: const BorderSide(color: outlineVariant, width: 1),
        ),
        margin: EdgeInsets.zero,
      ),
      dividerTheme: const DividerThemeData(
        color: outlineVariant,
        thickness: 1,
        space: 1,
      ),
    );
  }
}
