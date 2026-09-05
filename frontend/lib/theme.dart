import 'package:flutter/material.dart';

/// Палитра бренда SkyTime — из референса дизайна (см. `../style/`):
/// тёмно-бирюзовый навигационный/текстовый цвет, тёплый кремовый фон,
/// градиент teal → lime как акцент.
class SkyTimeColors {
  const SkyTimeColors._();

  static const navy = Color(0xFF032F37);
  static const cream = Color(0xFFF5F1E6);
  static const teal = Color(0xFF16B2AE);
  static const lime = Color(0xFF89D146);
  // Добавлены по новому референсу макета (dashboard с сайдбаром) — для
  // цветовых акцентов карточек участков сверх основной teal/lime пары.
  static const violet = Color(0xFF805FCD);
  static const pink = Color(0xFFCB81BD);
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

/// Тёмная тема — та же бренд-палитра, но фон/поверхности инвертированы
/// в тёмно-бирюзовый (navy), а не в кремовый. Акценты (teal/lime/violet/
/// pink) остаются теми же самыми — они уже достаточно яркие на тёмном фоне.
ThemeData buildSkyTimeDarkTheme() {
  const surface = Color(0xFF04252B);

  final colorScheme = ColorScheme.fromSeed(
    seedColor: SkyTimeColors.teal,
    brightness: Brightness.dark,
  ).copyWith(
    primary: SkyTimeColors.teal,
    onPrimary: SkyTimeColors.navy,
    secondary: SkyTimeColors.lime,
    onSecondary: SkyTimeColors.navy,
    tertiary: SkyTimeColors.violet,
    surface: surface,
    onSurface: SkyTimeColors.cream,
  );

  return ThemeData(
    useMaterial3: true,
    brightness: Brightness.dark,
    colorScheme: colorScheme,
    scaffoldBackgroundColor: SkyTimeColors.navy,
    cardColor: const Color(0xFF0A3A42),
    appBarTheme: const AppBarTheme(
      backgroundColor: Color(0xFF021B20),
      foregroundColor: SkyTimeColors.cream,
      iconTheme: IconThemeData(color: SkyTimeColors.cream),
      actionsIconTheme: IconThemeData(color: SkyTimeColors.cream),
    ),
    filledButtonTheme: FilledButtonThemeData(
      style: FilledButton.styleFrom(
        backgroundColor: SkyTimeColors.teal,
        foregroundColor: SkyTimeColors.navy,
      ),
    ),
    floatingActionButtonTheme: const FloatingActionButtonThemeData(
      backgroundColor: SkyTimeColors.teal,
      foregroundColor: SkyTimeColors.navy,
    ),
  );
}
