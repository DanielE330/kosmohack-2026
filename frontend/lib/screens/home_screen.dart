import 'dart:math' as math;
import 'dart:ui' as ui;

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../theme.dart';

/// Общий горизонтальный отступ от краёв экрана — один и тот же для
/// навигации и содержимого лендинга, чтобы левый и правый край совпадали.
const _kSidePadding = 96.0;

/// Главная — вход в продукт. До входа/регистрации доступна с корня ("/"),
/// сама карта живёт на "/map" (см. `app.dart`).
class HomeScreen extends StatelessWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: SkyTimeColors.cream,
      body: SafeArea(
        // Внешний LayoutBuilder знает высоту вьюпорта — по ней ограничиваем
        // высоту картинки справа, чтобы белая плашка с фичами тоже
        // помещалась в кадр без прокрутки на типичных экранах.
        child: LayoutBuilder(
          builder: (context, outer) {
            return SingleChildScrollView(
              child: ConstrainedBox(
                constraints: BoxConstraints(minHeight: outer.maxHeight),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    const _TopNav(),
                    Padding(
                      padding: const EdgeInsets.fromLTRB(_kSidePadding, 32, _kSidePadding, 24),
                      child: LayoutBuilder(
                        builder: (context, constraints) {
                          final wide = constraints.maxWidth > 860;
                          final hero = _HeroText(wide: wide);
                          final visualMaxHeight = wide
                              ? math.max(420.0, math.min(620.0, outer.maxHeight * 0.62))
                              : math.max(280.0, math.min(420.0, outer.maxHeight * 0.42));
                          final visual = ConstrainedBox(
                            constraints: BoxConstraints(maxHeight: visualMaxHeight),
                            child: const _HeroVisual(),
                          );
                          return Column(
                            crossAxisAlignment: CrossAxisAlignment.stretch,
                            children: [
                              wide
                                  ? Row(
                                      crossAxisAlignment: CrossAxisAlignment.center,
                                      children: [
                                        Expanded(flex: 5, child: hero),
                                        const SizedBox(width: 40),
                                        Expanded(flex: 6, child: visual),
                                      ],
                                    )
                                  : Column(
                                      crossAxisAlignment: CrossAxisAlignment.stretch,
                                      children: [
                                        hero,
                                        const SizedBox(height: 28),
                                        visual,
                                      ],
                                    ),
                              const SizedBox(height: 64),
                              const _FeatureStrip(),
                            ],
                          );
                        },
                      ),
                    ),
                  ],
                ),
              ),
            );
          },
        ),
      ),
    );
  }
}

class _TopNav extends StatelessWidget {
  const _TopNav();

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: _kSidePadding, vertical: 24),
      child: LayoutBuilder(
        builder: (context, constraints) {
          const logo = Image(
            image: AssetImage('assets/branding/skytime_logo_inverted.png'),
            height: 34,
          );
          const nav = Wrap(
            alignment: WrapAlignment.center,
            spacing: 22,
            runSpacing: 8,
            children: [
              _NavLabel('О ПРОДУКТЕ'),
              _NavLabel('ВОЗМОЖНОСТИ'),
              _NavLabel('ТЕХНОЛОГИИ'),
              _NavLabel('О НАС'),
            ],
          );
          const actions = _AuthActions();

          if (constraints.maxWidth <= 760) {
            return const Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [logo, actions],
                ),
                SizedBox(height: 14),
                Center(child: nav),
              ],
            );
          }
          // Stack + Align центрирует навигацию строго по центру бара
          // независимо от того, сколько места занимают лого слева и
          // кнопки справа.
          return const SizedBox(
            height: 44,
            child: Stack(
              alignment: Alignment.center,
              children: [
                Align(alignment: Alignment.centerLeft, child: logo),
                Align(child: nav),
                Align(alignment: Alignment.centerRight, child: actions),
              ],
            ),
          );
        },
      ),
    );
  }
}

class _NavLabel extends StatefulWidget {
  const _NavLabel(this.text);

  final String text;

  @override
  State<_NavLabel> createState() => _NavLabelState();
}

class _NavLabelState extends State<_NavLabel> {
  bool _hovered = false;

  @override
  Widget build(BuildContext context) {
    return MouseRegion(
      cursor: SystemMouseCursors.click,
      onEnter: (_) => setState(() => _hovered = true),
      onExit: (_) => setState(() => _hovered = false),
      child: AnimatedDefaultTextStyle(
        duration: const Duration(milliseconds: 150),
        style: TextStyle(
          fontSize: 12,
          fontWeight: FontWeight.w400,
          letterSpacing: 0.4,
          color: _hovered ? SkyTimeColors.navy : const Color(0x990E2B2C),
        ),
        child: Text(widget.text),
      ),
    );
  }
}

/// Кнопка-«таблетка» с градиентом teal→lime — общий стиль для акцентных
/// CTA лендинга («Регистрация» в шапке и «Начать наблюдение» в герое).
class _GradientPillButton extends StatelessWidget {
  const _GradientPillButton({
    required this.label,
    required this.onTap,
    this.icon,
    this.horizontalPadding = 24,
    this.verticalPadding = 13,
    this.fontSize = 13.5,
  });

  final String label;
  final VoidCallback onTap;
  final IconData? icon;
  final double horizontalPadding;
  final double verticalPadding;
  final double fontSize;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.transparent,
      child: InkWell(
        borderRadius: BorderRadius.circular(999),
        onTap: onTap,
        child: Ink(
          padding: EdgeInsets.symmetric(horizontal: horizontalPadding, vertical: verticalPadding),
          decoration: BoxDecoration(
            gradient: const LinearGradient(
              colors: [SkyTimeColors.teal, SkyTimeColors.lime],
            ),
            borderRadius: BorderRadius.circular(999),
            boxShadow: [
              BoxShadow(
                color: SkyTimeColors.teal.withValues(alpha: 0.4),
                blurRadius: 16,
                offset: const Offset(0, 6),
              ),
            ],
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(
                label,
                style: TextStyle(
                  fontWeight: FontWeight.w800,
                  fontSize: fontSize,
                  color: Colors.black,
                ),
              ),
              if (icon != null) ...[
                SizedBox(width: fontSize * 0.6),
                Icon(icon, size: fontSize + 3, color: Colors.black),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

/// Кнопки «Войти» / «Регистрация» — регистрация акцентная (градиент +
/// тень), «Войти» — контрастная тёмная обводка, чтобы обе явно читались
/// на фоне лёгкой навигации.
class _AuthActions extends StatelessWidget {
  const _AuthActions();

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        OutlinedButton(
          onPressed: () => context.push('/login'),
          style: OutlinedButton.styleFrom(
            foregroundColor: Colors.black,
            textStyle: const TextStyle(fontWeight: FontWeight.w800, fontSize: 13.5),
            side: const BorderSide(color: Colors.black, width: 1.6),
            shape: const StadiumBorder(),
            padding: const EdgeInsets.symmetric(horizontal: 22, vertical: 12),
          ),
          child: const Text('Войти'),
        ),
        const SizedBox(width: 12),
        _GradientPillButton(label: 'Регистрация', onTap: () => context.push('/register')),
      ],
    );
  }
}

class _HeroText extends StatelessWidget {
  const _HeroText({required this.wide});

  final bool wide;

  @override
  Widget build(BuildContext context) {
    final headingStyle = TextStyle(
      fontWeight: FontWeight.w800,
      fontSize: wide ? 56 : 40,
      height: 1.0,
      letterSpacing: -0.5,
      color: SkyTimeColors.navy,
    );
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        Text('ВРЕМЯ', style: headingStyle),
        Text('ВИДЕТЬ', style: headingStyle),
        // Тот же градиент teal→lime, что и на кнопке «Регистрация».
        ShaderMask(
          shaderCallback: (rect) => const LinearGradient(
            colors: [SkyTimeColors.teal, SkyTimeColors.lime],
          ).createShader(rect),
          child: Text('БОЛЬШЕ', style: headingStyle.copyWith(color: Colors.white)),
        ),
        const SizedBox(height: 20),
        ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 420),
          child: const Text(
            'Мониторинг вегетации сельхозполей по спутниковым снимкам NDVI: '
            'аномалии, прогноз урожайности и рекомендации по культурам.',
            style: TextStyle(
              fontSize: 15,
              height: 1.15,
              color: Color(0xB30E2B2C),
            ),
          ),
        ),
        const SizedBox(height: 28),
        _GradientPillButton(
          label: 'Начать наблюдение',
          onTap: () => context.go('/map'),
          icon: Icons.arrow_forward,
          horizontalPadding: 34,
          verticalPadding: 20,
          fontSize: 15,
        ),
        const SizedBox(height: 12),
        ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 340),
          child: const Text(
            'Откроется карта — выберите свой полигон, и появится страница с '
            'анализом состояния поля.',
            style: TextStyle(fontSize: 11.5, color: Color(0x730E2B2C)),
          ),
        ),
      ],
    );
  }
}

/// Временный плейсхолдер вместо прежней декоративной панели — «мёртвый»
/// метеор всегда на виду, а при наведении вокруг курсора мягко проступает
/// «живой» (зелёный): не жёсткий круг-лупа, а растушёванное пятно —
/// верхний слой становится прозрачным к краям через радиальный
/// градиент-маску (без резкой границы).
class _HeroVisual extends StatefulWidget {
  const _HeroVisual();

  @override
  State<_HeroVisual> createState() => _HeroVisualState();
}

class _HeroVisualState extends State<_HeroVisual> {
  static const _revealRadius = 150.0;

  Offset? _hoverPos;

  @override
  Widget build(BuildContext context) {
    return MouseRegion(
      onHover: (event) => setState(() => _hoverPos = event.localPosition),
      onExit: (_) => setState(() => _hoverPos = null),
      child: Stack(
        fit: StackFit.expand,
        children: [
          const Center(
            child: Image(
              image: AssetImage('assets/branding/die-meteor.png'),
              fit: BoxFit.contain,
            ),
          ),
          if (_hoverPos != null)
            IgnorePointer(
              child: ShaderMask(
                blendMode: BlendMode.dstIn,
                shaderCallback: (bounds) => ui.Gradient.radial(
                  _hoverPos!,
                  _revealRadius,
                  // Плато полной непрозрачности почти до края круга — само
                  // изображение около курсора остаётся чётким, растушёвка
                  // только в последней четверти радиуса.
                  const [Colors.white, Colors.white, Colors.transparent],
                  const [0.0, 0.72, 1.0],
                ),
                child: const Center(
                  child: Image(
                    image: AssetImage('assets/branding/meteor.png'),
                    fit: BoxFit.contain,
                  ),
                ),
              ),
            ),
        ],
      ),
    );
  }
}

class _FeatureStrip extends StatelessWidget {
  const _FeatureStrip();

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 20),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(20),
        // Без тени по требованию — раньше здесь была box-shadow.
      ),
      child: Wrap(
        spacing: 32,
        runSpacing: 20,
        children: const [
          _FeatureItem(
            icon: Icons.satellite_alt_outlined,
            iconColor: SkyTimeColors.teal,
            label: 'СПУТНИКОВЫЕ ДАННЫЕ',
            value: 'Sentinel-2, 10 м/пиксель',
          ),
          _FeatureItem(
            icon: Icons.update,
            iconColor: Color(0xFF537526),
            label: 'ОБНОВЛЕНИЕ ДАННЫХ',
            value: 'Каждые 1–3 дня',
          ),
          _FeatureItem(
            icon: Icons.show_chart,
            iconColor: Color(0xFF805FCD),
            label: 'ВОССТАНОВЛЕНИЕ ПРОПУСКОВ',
            value: 'Модель закрывает разрывы NDVI',
          ),
          _FeatureItem(
            icon: Icons.warning_amber_rounded,
            iconColor: Color(0xFF96438A),
            label: 'ДЕТЕКЦИЯ АНОМАЛИЙ',
            value: 'Оповещение по Z-score',
          ),
        ],
      ),
    );
  }
}

class _FeatureItem extends StatelessWidget {
  const _FeatureItem({
    required this.icon,
    required this.iconColor,
    required this.label,
    required this.value,
  });

  final IconData icon;
  final Color iconColor;
  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return ConstrainedBox(
      constraints: const BoxConstraints(minWidth: 200, maxWidth: 260),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, size: 20, color: iconColor),
          const SizedBox(width: 12),
          Flexible(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  label,
                  style: const TextStyle(
                    fontSize: 10,
                    fontWeight: FontWeight.w700,
                    letterSpacing: 0.4,
                    color: Color(0x800E2B2C),
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  value,
                  style: const TextStyle(
                    fontSize: 13,
                    fontWeight: FontWeight.w700,
                    color: SkyTimeColors.navy,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
