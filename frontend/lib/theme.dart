import 'package:flutter/material.dart';

/// Палитра бренда SkyTime — из референса дизайна (см. `../style/`):
/// тёмно-бирюзовый навигационный/текстовый цвет, тёплый кремовый фон,
/// градиент teal → lime как акцент.
class SkyTimeColors {
  const SkyTimeColors._();

  static const navy = Color(0xFF0E2B2C);
  static const cream = Color(0xFFF5F1E7);
  static const teal = Color(0xFF2BC4C0);
  static const lime = Color(0xFF8DC63F);
}

ThemeData buildSkyTimeTheme() {
  final colorScheme = ColorScheme.fromSeed(
    seedColor: SkyTimeColors.teal,
    brightness: Brightness.light,
  ).copyWith(
    primary: SkyTimeColors.navy,
    onPrimary: SkyTimeColors.cream,
    secondary: SkyTimeColors.teal,
    onSecondary: SkyTimeColors.navy,
    tertiary: SkyTimeColors.lime,
    surface: SkyTimeColors.cream,
    onSurface: SkyTimeColors.navy,
  );

  return ThemeData(
    useMaterial3: true,
    colorScheme: colorScheme,
    scaffoldBackgroundColor: SkyTimeColors.cream,
    appBarTheme: const AppBarTheme(
      backgroundColor: SkyTimeColors.navy,
      foregroundColor: SkyTimeColors.cream,
      iconTheme: IconThemeData(color: SkyTimeColors.cream),
      actionsIconTheme: IconThemeData(color: SkyTimeColors.cream),
    ),
    filledButtonTheme: FilledButtonThemeData(
      style: FilledButton.styleFrom(
        backgroundColor: SkyTimeColors.navy,
        foregroundColor: SkyTimeColors.cream,
      ),
    ),
    floatingActionButtonTheme: const FloatingActionButtonThemeData(
      backgroundColor: SkyTimeColors.navy,
      foregroundColor: SkyTimeColors.cream,
    ),
  );
}
