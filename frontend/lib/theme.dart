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

  // Оттенки тёмной темы и тёмных блоков светлой (hero на главной) —
  // раньше они были разбросаны по экранам хардкодами, теперь живут здесь,
  // чтобы тёмные секции везде совпадали по цвету.
  static const navyDeep = Color(0xFF021B20);
  static const navySurface = Color(0xFF04252B);
  static const navyCard = Color(0xFF0A3A42);

  /// Градиент акцента (teal → lime) — тот же, что на hero-заголовке
  /// главной; вынесен, чтобы не расходился между экранами.
  static const accentGradient = LinearGradient(colors: [teal, lime]);
}

/// Единые скругления и отступы. Раньше каждый экран выбирал радиус сам
/// (8/12/14/16/20/999 вперемешку) — из-за этого одинаковые по смыслу
/// элементы выглядели по-разному. Здесь один набор на всё приложение.
class SkyTimeRadii {
  const SkyTimeRadii._();

  /// Мелкие элементы: чипы-«таблетки» статуса, бейджи.
  static const small = 10.0;

  /// Кнопки, поля ввода, элементы списков.
  static const medium = 14.0;

  /// Карточки и панели.
  static const large = 18.0;

  /// Диалоги и крупные «стеклянные» блоки.
  static const xlarge = 24.0;

  /// Полностью круглые «таблетки».
  static const pill = 999.0;
}

/// Типографика: одна шкала на обе темы. Отличается от дефолтной Material
/// более плотными заголовками (w800 + отрицательный letterSpacing) — так
/// же, как набран hero на главной, чтобы остальные экраны не выглядели
/// «другим продуктом».
TextTheme _skyTimeTextTheme(TextTheme base, Color onSurface) {
  final muted = onSurface.withValues(alpha: 0.66);
  return base.copyWith(
    displaySmall: base.displaySmall?.copyWith(
      fontWeight: FontWeight.w800,
      letterSpacing: -1,
      height: 1.06,
      color: onSurface,
    ),
    headlineMedium: base.headlineMedium?.copyWith(
      fontWeight: FontWeight.w800,
      letterSpacing: -0.8,
      height: 1.1,
      color: onSurface,
    ),
    headlineSmall: base.headlineSmall?.copyWith(
      fontWeight: FontWeight.w800,
      letterSpacing: -0.5,
      color: onSurface,
    ),
    titleLarge: base.titleLarge?.copyWith(
      fontWeight: FontWeight.w800,
      letterSpacing: -0.3,
      color: onSurface,
    ),
    titleMedium: base.titleMedium?.copyWith(
      fontWeight: FontWeight.w700,
      letterSpacing: -0.2,
      color: onSurface,
    ),
    titleSmall: base.titleSmall?.copyWith(fontWeight: FontWeight.w700, color: onSurface),
    bodyLarge: base.bodyLarge?.copyWith(height: 1.5, color: onSurface),
    bodyMedium: base.bodyMedium?.copyWith(height: 1.5, color: onSurface),
    bodySmall: base.bodySmall?.copyWith(height: 1.45, color: muted),
    labelLarge: base.labelLarge?.copyWith(fontWeight: FontWeight.w700, letterSpacing: 0),
    labelMedium: base.labelMedium?.copyWith(fontWeight: FontWeight.w700, color: muted),
    labelSmall: base.labelSmall?.copyWith(fontWeight: FontWeight.w700, color: muted),
  );
}

/// Общая часть светлой и тёмной тем. Всё, что отличается только цветом,
/// собирается отсюда из [scheme] — поэтому «улучшить кнопки/карточки»
/// достаточно один раз, а не дважды.
ThemeData _buildTheme({
  required ColorScheme scheme,
  required Color scaffoldBackground,
  required Color cardColor,
  required Color inputFill,
  required Color appBarBackground,
}) {
  final isDark = scheme.brightness == Brightness.dark;
  final base = ThemeData(useMaterial3: true, brightness: scheme.brightness, colorScheme: scheme);
  final onSurface = scheme.onSurface;
  final border = BorderSide(color: scheme.outlineVariant);

  // Единая «мягкая» тень карточек: у Material 3 по умолчанию она либо
  // отсутствует, либо тонирована surfaceTint — на кремовом фоне это
  // выглядело грязно, поэтому берём свою, почти прозрачную.
  final softShadow = isDark
      ? Colors.black.withValues(alpha: 0.35)
      : SkyTimeColors.navy.withValues(alpha: 0.08);

  OutlineInputBorder inputBorder(Color color, [double width = 1]) => OutlineInputBorder(
        borderRadius: BorderRadius.circular(SkyTimeRadii.medium),
        borderSide: BorderSide(color: color, width: width),
      );

  return base.copyWith(
    scaffoldBackgroundColor: scaffoldBackground,
    canvasColor: scaffoldBackground,
    cardColor: cardColor,
    dividerColor: scheme.outlineVariant,
    shadowColor: softShadow,
    hintColor: onSurface.withValues(alpha: 0.6),
    textTheme: _skyTimeTextTheme(base.textTheme, onSurface),
    primaryTextTheme: _skyTimeTextTheme(base.primaryTextTheme, scheme.onPrimary),

    appBarTheme: AppBarTheme(
      backgroundColor: appBarBackground,
      foregroundColor: SkyTimeColors.cream,
      elevation: 0,
      // Без этого AppBar при скролле сам подмешивает surfaceTint и
      // «выцветает» из бренд-цвета в сиреневый M3-оттенок.
      scrolledUnderElevation: 0,
      surfaceTintColor: Colors.transparent,
      centerTitle: false,
      titleSpacing: 20,
      iconTheme: const IconThemeData(color: SkyTimeColors.cream),
      actionsIconTheme: const IconThemeData(color: SkyTimeColors.cream),
      titleTextStyle: const TextStyle(
        color: SkyTimeColors.cream,
        fontSize: 19,
        fontWeight: FontWeight.w800,
        letterSpacing: -0.3,
      ),
    ),

    cardTheme: CardThemeData(
      color: cardColor,
      surfaceTintColor: Colors.transparent,
      elevation: 0,
      // Отступы карточки намеренно оставлены материаловскими по умолчанию:
      // Card используется и как плавающая панель поверх карты, где своя
      // геометрия отступов уже подобрана на месте.
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(SkyTimeRadii.large),
        side: border,
      ),
    ),

    // Кнопки: одна геометрия на все три вида, отличается только заливка.
    filledButtonTheme: FilledButtonThemeData(
      style: FilledButton.styleFrom(
        backgroundColor: isDark ? SkyTimeColors.teal : SkyTimeColors.navy,
        foregroundColor: isDark ? SkyTimeColors.navy : SkyTimeColors.cream,
        disabledBackgroundColor: onSurface.withValues(alpha: 0.12),
        disabledForegroundColor: onSurface.withValues(alpha: 0.38),
        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 14),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(SkyTimeRadii.medium)),
        textStyle: const TextStyle(fontSize: 14, fontWeight: FontWeight.w700, letterSpacing: 0),
      ),
    ),
    outlinedButtonTheme: OutlinedButtonThemeData(
      style: OutlinedButton.styleFrom(
        foregroundColor: isDark ? SkyTimeColors.cream : SkyTimeColors.navy,
        side: BorderSide(color: onSurface.withValues(alpha: 0.22)),
        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 14),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(SkyTimeRadii.medium)),
        textStyle: const TextStyle(fontSize: 14, fontWeight: FontWeight.w700, letterSpacing: 0),
      ).copyWith(
        // Наведение подсвечивает акцентом, а не серым Material-оверлеем —
        // иначе на кремовом фоне hover почти не читается.
        overlayColor: WidgetStateProperty.resolveWith(
          (states) => states.contains(WidgetState.hovered)
              ? SkyTimeColors.teal.withValues(alpha: 0.10)
              : null,
        ),
      ),
    ),
    textButtonTheme: TextButtonThemeData(
      style: TextButton.styleFrom(
        foregroundColor: isDark ? SkyTimeColors.teal : SkyTimeColors.navy,
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(SkyTimeRadii.small)),
        textStyle: const TextStyle(fontSize: 13.5, fontWeight: FontWeight.w700, letterSpacing: 0),
      ),
    ),
    iconButtonTheme: IconButtonThemeData(
      style: IconButton.styleFrom(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(SkyTimeRadii.small)),
      ),
    ),

    inputDecorationTheme: InputDecorationTheme(
      // Заливка вместо голого подчёркивания: поля становятся видимыми
      // блоками, а форма — читаемой сеткой (см. экраны входа/регистрации).
      filled: true,
      fillColor: inputFill,
      contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 15),
      border: inputBorder(scheme.outlineVariant),
      enabledBorder: inputBorder(scheme.outlineVariant),
      focusedBorder: inputBorder(SkyTimeColors.teal, 1.6),
      errorBorder: inputBorder(scheme.error),
      focusedErrorBorder: inputBorder(scheme.error, 1.6),
      labelStyle: TextStyle(color: onSurface.withValues(alpha: 0.7)),
      floatingLabelStyle: const TextStyle(color: SkyTimeColors.teal, fontWeight: FontWeight.w700),
      hintStyle: TextStyle(color: onSurface.withValues(alpha: 0.45)),
      prefixIconColor: onSurface.withValues(alpha: 0.55),
      suffixIconColor: onSurface.withValues(alpha: 0.55),
    ),

    chipTheme: ChipThemeData(
      backgroundColor: isDark ? Colors.white.withValues(alpha: 0.06) : SkyTimeColors.cream,
      selectedColor: SkyTimeColors.teal.withValues(alpha: 0.18),
      side: border,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(SkyTimeRadii.pill)),
      labelStyle: TextStyle(fontSize: 12.5, fontWeight: FontWeight.w700, color: onSurface),
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
    ),

    listTileTheme: ListTileThemeData(
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(SkyTimeRadii.medium)),
      iconColor: onSurface.withValues(alpha: 0.7),
      titleTextStyle: TextStyle(fontSize: 14.5, fontWeight: FontWeight.w700, color: onSurface),
      subtitleTextStyle: TextStyle(fontSize: 12.5, color: onSurface.withValues(alpha: 0.66)),
    ),

    dividerTheme: DividerThemeData(color: scheme.outlineVariant, thickness: 1, space: 1),

    dialogTheme: DialogThemeData(
      backgroundColor: cardColor,
      surfaceTintColor: Colors.transparent,
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(SkyTimeRadii.xlarge),
        side: border,
      ),
      titleTextStyle: TextStyle(
        fontSize: 19,
        fontWeight: FontWeight.w800,
        letterSpacing: -0.3,
        color: onSurface,
      ),
    ),

    // Снэкбар всегда тёмный (в обеих темах) — это уведомление поверх
    // контента, ему полезно контрастировать с фоном страницы.
    snackBarTheme: SnackBarThemeData(
      behavior: SnackBarBehavior.floating,
      backgroundColor: SkyTimeColors.navyDeep,
      contentTextStyle: const TextStyle(color: SkyTimeColors.cream, fontSize: 13.5),
      actionTextColor: SkyTimeColors.lime,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(SkyTimeRadii.medium)),
      insetPadding: const EdgeInsets.all(16),
    ),

    tooltipTheme: TooltipThemeData(
      decoration: BoxDecoration(
        color: SkyTimeColors.navyDeep,
        borderRadius: BorderRadius.circular(SkyTimeRadii.small),
      ),
      textStyle: const TextStyle(color: SkyTimeColors.cream, fontSize: 12),
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 7),
      waitDuration: const Duration(milliseconds: 400),
    ),

    dataTableTheme: DataTableThemeData(
      headingTextStyle: TextStyle(
        fontSize: 12,
        fontWeight: FontWeight.w800,
        letterSpacing: 0.3,
        color: onSurface.withValues(alpha: 0.62),
      ),
      dataTextStyle: TextStyle(fontSize: 13.5, color: onSurface),
      dividerThickness: 1,
      headingRowColor: WidgetStatePropertyAll(
        isDark ? Colors.white.withValues(alpha: 0.03) : SkyTimeColors.cream,
      ),
      // Наведение на строку подсказывает, что она кликабельна.
      dataRowColor: WidgetStateProperty.resolveWith((states) {
        if (states.contains(WidgetState.selected)) {
          return SkyTimeColors.teal.withValues(alpha: 0.12);
        }
        if (states.contains(WidgetState.hovered)) {
          return SkyTimeColors.teal.withValues(alpha: 0.06);
        }
        return null;
      }),
    ),

    floatingActionButtonTheme: FloatingActionButtonThemeData(
      backgroundColor: isDark ? SkyTimeColors.teal : SkyTimeColors.navy,
      foregroundColor: isDark ? SkyTimeColors.navy : SkyTimeColors.cream,
      elevation: 2,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(SkyTimeRadii.large)),
    ),

    // Мелкие управляющие элементы — на бренд-акцент, а не на дефолтный
    // фиолетовый M3.
    switchTheme: SwitchThemeData(
      thumbColor: WidgetStateProperty.resolveWith(
        (states) => states.contains(WidgetState.selected) ? Colors.white : null,
      ),
      trackColor: WidgetStateProperty.resolveWith(
        (states) => states.contains(WidgetState.selected) ? SkyTimeColors.teal : null,
      ),
    ),
    checkboxTheme: CheckboxThemeData(
      fillColor: WidgetStateProperty.resolveWith(
        (states) => states.contains(WidgetState.selected) ? SkyTimeColors.teal : null,
      ),
      checkColor: const WidgetStatePropertyAll(Colors.white),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(5)),
    ),
    radioTheme: RadioThemeData(
      fillColor: WidgetStateProperty.resolveWith(
        (states) => states.contains(WidgetState.selected) ? SkyTimeColors.teal : null,
      ),
    ),
    sliderTheme: SliderThemeData(
      activeTrackColor: SkyTimeColors.teal,
      thumbColor: SkyTimeColors.teal,
      inactiveTrackColor: onSurface.withValues(alpha: 0.16),
      overlayColor: SkyTimeColors.teal.withValues(alpha: 0.14),
    ),
    progressIndicatorTheme: const ProgressIndicatorThemeData(
      color: SkyTimeColors.teal,
      circularTrackColor: Colors.transparent,
    ),
    tabBarTheme: TabBarThemeData(
      labelColor: isDark ? SkyTimeColors.cream : SkyTimeColors.navy,
      unselectedLabelColor: onSurface.withValues(alpha: 0.6),
      indicatorColor: SkyTimeColors.teal,
      dividerColor: scheme.outlineVariant,
      labelStyle: const TextStyle(fontSize: 13.5, fontWeight: FontWeight.w700),
    ),
    navigationBarTheme: NavigationBarThemeData(
      backgroundColor: cardColor,
      indicatorColor: SkyTimeColors.teal.withValues(alpha: 0.18),
      surfaceTintColor: Colors.transparent,
      elevation: 0,
    ),
  );
}

ThemeData buildSkyTimeTheme() {
  final scheme = ColorScheme.fromSeed(
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
    // Карточки/панели — белые поверх кремового фона: так между «листом» и
    // «столом» есть разница даже без теней.
    surfaceContainerLowest: Colors.white,
    surfaceContainerLow: Colors.white,
    surfaceContainer: const Color(0xFFFBF9F2),
    surfaceContainerHigh: SkyTimeColors.cream,
    surfaceContainerHighest: const Color(0xFFEDE7D6),
    outline: SkyTimeColors.navy.withValues(alpha: 0.28),
    outlineVariant: SkyTimeColors.navy.withValues(alpha: 0.12),
  );

  return _buildTheme(
    scheme: scheme,
    scaffoldBackground: SkyTimeColors.cream,
    cardColor: Colors.white,
    inputFill: Colors.white,
    appBarBackground: SkyTimeColors.navy,
  );
}

/// Тёмная тема — та же бренд-палитра, но фон/поверхности инвертированы
/// в тёмно-бирюзовый (navy), а не в кремовый. Акценты (teal/lime/violet/
/// pink) остаются теми же самыми — они уже достаточно яркие на тёмном фоне.
ThemeData buildSkyTimeDarkTheme() {
  final scheme = ColorScheme.fromSeed(
    seedColor: SkyTimeColors.teal,
    brightness: Brightness.dark,
  ).copyWith(
    primary: SkyTimeColors.teal,
    onPrimary: SkyTimeColors.navy,
    secondary: SkyTimeColors.lime,
    onSecondary: SkyTimeColors.navy,
    tertiary: SkyTimeColors.violet,
    surface: SkyTimeColors.navySurface,
    onSurface: SkyTimeColors.cream,
    surfaceContainerLowest: SkyTimeColors.navyDeep,
    surfaceContainerLow: SkyTimeColors.navySurface,
    surfaceContainer: SkyTimeColors.navyCard,
    surfaceContainerHigh: SkyTimeColors.navyCard,
    surfaceContainerHighest: const Color(0xFF0E4650),
    outline: SkyTimeColors.cream.withValues(alpha: 0.26),
    outlineVariant: SkyTimeColors.cream.withValues(alpha: 0.13),
  );

  return _buildTheme(
    scheme: scheme,
    scaffoldBackground: SkyTimeColors.navy,
    cardColor: SkyTimeColors.navyCard,
    inputFill: Colors.white.withValues(alpha: 0.05),
    appBarBackground: SkyTimeColors.navyDeep,
  );
}
