import 'dart:math' as math;
import 'dart:ui' as ui;

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../theme.dart';

/// Общий горизонтальный отступ от краёв экрана — один и тот же для
/// навигации и содержимого лендинга, чтобы левый и правый край совпадали.
const _kSidePadding = 96.0;

/// Якоря секций лендинга — на них ведут пункты навигации в `_TopNav`.
final _aboutKey = GlobalKey();
final _featuresKey = GlobalKey();
final _techKey = GlobalKey();
final _teamKey = GlobalKey();

/// Плавно скроллит к секции по её якорю (если она уже отрисована).
void _scrollToSection(GlobalKey key) {
  final ctx = key.currentContext;
  if (ctx == null) return;
  Scrollable.ensureVisible(
    ctx,
    duration: const Duration(milliseconds: 500),
    curve: Curves.easeInOut,
    alignment: 0.05,
  );
}

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
                              _Section(
                                sectionKey: _featuresKey,
                                title: 'ВОЗМОЖНОСТИ',
                                child: const _FeatureStrip(),
                              ),
                              const SizedBox(height: 64),
                              _Section(
                                sectionKey: _aboutKey,
                                title: 'О ПРОДУКТЕ',
                                child: const _AboutProductBody(),
                              ),
                              const SizedBox(height: 64),
                              _Section(
                                sectionKey: _techKey,
                                title: 'ТЕХНОЛОГИИ',
                                child: const _TechnologiesBody(),
                              ),
                              const SizedBox(height: 64),
                              _Section(
                                sectionKey: _teamKey,
                                title: 'О НАС',
                                child: const _AboutUsBody(),
                              ),
                              const SizedBox(height: 48),
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

/// Обёртка секции лендинга: заголовок + произвольное содержимое,
/// с `sectionKey`, на который наводится скролл из `_TopNav`.
class _Section extends StatelessWidget {
  const _Section({
    required this.sectionKey,
    required this.title,
    required this.child,
  });

  final GlobalKey sectionKey;
  final String title;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    return Column(
      key: sectionKey,
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text(
          title,
          style: const TextStyle(
            fontSize: 13,
            fontWeight: FontWeight.w800,
            letterSpacing: 1.2,
            color: SkyTimeColors.teal,
          ),
        ),
        const SizedBox(height: 16),
        child,
      ],
    );
  }
}

class _AboutProductBody extends StatelessWidget {
  const _AboutProductBody();

  @override
  Widget build(BuildContext context) {
    return _BentoGrid(
      big: const _BentoBigCard(
        badge: 'КАК ЭТО РАБОТАЕТ',
        heading: 'КАРТА → АНАЛИЗ\n→ РЕКОМЕНДАЦИЯ.',
        description:
            'Отмечаете полигон на карте — дальше система сама следит за его '
            'состоянием по снимкам Sentinel-2: считает NDVI, восстанавливает '
            'пропуски и подсвечивает отклонения.',
        decorationIcon: Icons.map_outlined,
      ),
      stat: const _BentoStatCard(
        label: 'РАЗРЕШЕНИЕ СНИМКОВ',
        value: '10 м/px',
        progress: 0.85,
      ),
      dark: const _BentoDarkCard(
        icon: Icons.calendar_month,
        title: 'История поля',
        subtitle: 'Полный архив NDVI по каждому полигону',
      ),
      cta: _BentoCtaCard(
        title: 'НАЧАТЬ НАБЛЮДЕНИЕ',
        subtitle: 'Отметьте свой полигон — первый отчёт появится за минуты.',
        onTap: () => context.go('/map'),
      ),
    );
  }
}

class _TechnologiesBody extends StatelessWidget {
  const _TechnologiesBody();

  @override
  Widget build(BuildContext context) {
    return _BentoGrid(
      big: const _BentoBigCard(
        badge: 'ОТКУДА ДАННЫЕ',
        heading: 'SENTINEL-2 +\nGOOGLE EARTH ENGINE.',
        description:
            'Открытые спутниковые данные и облачная инфраструктура для их '
            'обработки — без своих спутников и дорогих лицензий.',
        decorationIcon: Icons.satellite_alt_outlined,
      ),
      stat: const _BentoStatCard(
        label: 'ТОЧНОСТЬ GAP-FILLING',
        value: '94%',
        progress: 0.94,
      ),
      dark: const _BentoDarkCard(
        icon: Icons.dns_outlined,
        title: 'Backend',
        subtitle: 'Python (FastAPI) + Flutter web/desktop',
      ),
      cta: const _BentoCtaCard(
        title: 'ML-МОДЕЛИ',
        subtitle: 'Gap-filling NDVI и статистическая детекция аномалий по истории поля.',
        icon: Icons.auto_graph,
      ),
    );
  }
}

/// Общий скруглённый контейнер для «bento»-карточек секции «О нас» —
/// одна и та же геометрия (радиус, тень отсутствует по стилю сайта),
/// цвет и содержимое задаёт вызывающий код.
class _BentoCard extends StatelessWidget {
  const _BentoCard({required this.color, required this.child});

  final Color color;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(28),
      decoration: BoxDecoration(
        color: color,
        borderRadius: BorderRadius.circular(20),
        border: color == Colors.white ? Border.all(color: const Color(0x14032F37)) : null,
      ),
      child: child,
    );
  }
}

/// «О нас» — тот же bento-грид, что и у остальных трёх секций лендинга,
/// просто со своим набором карточек (миссия/рост/модель/сообщество).
class _AboutUsBody extends StatelessWidget {
  const _AboutUsBody();

  @override
  Widget build(BuildContext context) {
    return _BentoGrid(
      big: const _BentoBigCard(
        badge: 'ШИРОКИЙ ОХВАТ',
        heading: 'ВЛИЯНИЕ\nБЕЗ ГРАНИЦ.',
        description:
            'Мы помогаем агрономам следить более чем за 10 000 га полей по '
            'спутниковым снимкам — без датчиков и выездов на месте.',
      ),
      stat: const _BentoStatCard(
        label: 'ПРИРОСТ УРОЖАЙНОСТИ',
        value: '+18%',
        progress: 0.8,
      ),
      dark: const _BentoDarkCard(
        icon: Icons.insights,
        title: 'NDVI Gap-Filling',
        subtitle: 'Модель стабильна · v4',
      ),
      cta: const _BentoCtaCard(
        title: 'ПРИСОЕДИНЯЙТЕСЬ К СООБЩЕСТВУ',
        subtitle: 'Свяжитесь с агрономами, которые уже наблюдают за полями в SkyTime.',
      ),
    );
  }
}

/// Общая раскладка «bento»-секций лендинга: крупная карточка слева (5/9
/// ширины), две поменьше в верхнем ряду справа и одна на всю ширину правой
/// колонки снизу. Один и тот же скелет использует «Возможности», «О
/// продукте», «Технологии» и «О нас» — так у них общий визуальный язык, а
/// различается только содержимое карточек. На узких экранах всё складывается
/// в одну колонку.
class _BentoGrid extends StatelessWidget {
  const _BentoGrid({
    required this.big,
    required this.stat,
    required this.dark,
    required this.cta,
  });

  final Widget big;
  final Widget stat;
  final Widget dark;
  final Widget cta;

  static const _gap = 20.0;
  static const _rowHeight = 210.0;

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final wide = constraints.maxWidth > 760;
        if (!wide) {
          return Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              big,
              const SizedBox(height: _gap),
              stat,
              const SizedBox(height: _gap),
              dark,
              const SizedBox(height: _gap),
              cta,
            ],
          );
        }
        return SizedBox(
          height: _rowHeight * 2 + _gap,
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Expanded(flex: 5, child: big),
              const SizedBox(width: _gap),
              Expanded(
                flex: 4,
                child: Column(
                  children: [
                    SizedBox(
                      height: _rowHeight,
                      child: Row(
                        children: [
                          Expanded(child: stat),
                          const SizedBox(width: _gap),
                          Expanded(child: dark),
                        ],
                      ),
                    ),
                    const SizedBox(height: _gap),
                    SizedBox(height: _rowHeight, child: cta),
                  ],
                ),
              ),
            ],
          ),
        );
      },
    );
  }
}

/// Крупная карточка bento-секции: бейдж + заголовок + описание, с
/// декоративной иконкой на фоне, которая мягко разворачивается при
/// наведении (тот же приём, что и hover в `_NavLabel` и `_HeroVisual`, —
/// здесь через поворот, а не смену прозрачности).
class _BentoBigCard extends StatefulWidget {
  const _BentoBigCard({
    required this.badge,
    required this.heading,
    required this.description,
    this.decorationIcon = Icons.auto_awesome,
  });

  final String badge;
  final String heading;
  final String description;
  final IconData decorationIcon;

  @override
  State<_BentoBigCard> createState() => _BentoBigCardState();
}

class _BentoBigCardState extends State<_BentoBigCard> {
  bool _hovered = false;

  @override
  Widget build(BuildContext context) {
    return MouseRegion(
      onEnter: (_) => setState(() => _hovered = true),
      onExit: (_) => setState(() => _hovered = false),
      child: _BentoCard(
        color: Colors.white,
        child: Stack(
          clipBehavior: Clip.none,
          children: [
            Positioned(
              right: -60,
              bottom: -60,
              child: IgnorePointer(
                child: AnimatedRotation(
                  turns: _hovered ? 0.5 : 0,
                  duration: const Duration(milliseconds: 800),
                  curve: Curves.easeInOut,
                  child: Icon(
                    widget.decorationIcon,
                    size: 220,
                    color: SkyTimeColors.navy.withValues(alpha: 0.05),
                  ),
                ),
              ),
            ),
            Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
                      decoration: BoxDecoration(
                        color: SkyTimeColors.violet,
                        borderRadius: BorderRadius.circular(999),
                      ),
                      child: Text(
                        widget.badge,
                        style: const TextStyle(
                          fontSize: 10,
                          fontWeight: FontWeight.w900,
                          letterSpacing: 1.0,
                          color: Colors.white,
                        ),
                      ),
                    ),
                    const SizedBox(height: 20),
                    Text(
                      widget.heading,
                      style: const TextStyle(
                        fontSize: 34,
                        fontWeight: FontWeight.w900,
                        height: 1.05,
                        letterSpacing: -0.5,
                        color: SkyTimeColors.navy,
                      ),
                    ),
                  ],
                ),
                ConstrainedBox(
                  constraints: const BoxConstraints(maxWidth: 360),
                  child: Text(
                    widget.description,
                    style: const TextStyle(fontSize: 15, height: 1.5, color: Color(0x990E2B2C)),
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _BentoStatCard extends StatelessWidget {
  const _BentoStatCard({
    required this.label,
    required this.value,
    required this.progress,
  });

  final String label;
  final String value;
  final double progress;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(22),
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [SkyTimeColors.teal, SkyTimeColors.lime],
        ),
        borderRadius: BorderRadius.circular(20),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(
            label,
            style: const TextStyle(
              fontSize: 10,
              fontWeight: FontWeight.w900,
              letterSpacing: 0.8,
              color: Colors.black54,
            ),
          ),
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                value,
                style: const TextStyle(
                  fontSize: 32,
                  fontWeight: FontWeight.w900,
                  letterSpacing: -1,
                  color: Colors.black,
                ),
              ),
              const SizedBox(height: 8),
              Stack(
                children: [
                  Container(
                    height: 6,
                    decoration: BoxDecoration(
                      color: Colors.white.withValues(alpha: 0.35),
                      borderRadius: BorderRadius.circular(999),
                    ),
                  ),
                  FractionallySizedBox(
                    widthFactor: progress,
                    child: Container(
                      height: 6,
                      decoration: BoxDecoration(
                        color: Colors.white,
                        borderRadius: BorderRadius.circular(999),
                        boxShadow: [
                          BoxShadow(
                            color: Colors.white.withValues(alpha: 0.8),
                            blurRadius: 10,
                          ),
                        ],
                      ),
                    ),
                  ),
                ],
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _BentoDarkCard extends StatelessWidget {
  const _BentoDarkCard({
    required this.icon,
    required this.title,
    required this.subtitle,
  });

  final IconData icon;
  final String title;
  final String subtitle;

  @override
  Widget build(BuildContext context) {
    return _BentoCard(
      color: SkyTimeColors.navy,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisAlignment: MainAxisAlignment.center,
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 40,
            height: 40,
            decoration: BoxDecoration(
              color: SkyTimeColors.violet,
              borderRadius: BorderRadius.circular(12),
            ),
            child: Center(child: Icon(icon, size: 20, color: Colors.white)),
          ),
          const SizedBox(height: 16),
          Text(
            title,
            style: const TextStyle(
              fontSize: 18,
              fontWeight: FontWeight.w800,
              height: 1.2,
              color: Colors.white,
            ),
          ),
          const SizedBox(height: 6),
          Text(
            subtitle,
            style: const TextStyle(fontSize: 11, color: Color(0x99F5F1E6)),
          ),
        ],
      ),
    );
  }
}

class _BentoCtaCard extends StatelessWidget {
  const _BentoCtaCard({
    required this.title,
    required this.subtitle,
    this.icon = Icons.arrow_forward,
    this.onTap,
  });

  final String title;
  final String subtitle;
  final IconData icon;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final content = Container(
      padding: const EdgeInsets.symmetric(horizontal: 28, vertical: 24),
      decoration: BoxDecoration(
        color: SkyTimeColors.violet,
        borderRadius: BorderRadius.circular(20),
      ),
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  title,
                  style: const TextStyle(
                    fontSize: 18,
                    fontWeight: FontWeight.w900,
                    letterSpacing: -0.2,
                    height: 1.15,
                    color: Colors.white,
                  ),
                ),
                const SizedBox(height: 8),
                Text(
                  subtitle,
                  style: TextStyle(fontSize: 12.5, height: 1.4, color: Colors.white.withValues(alpha: 0.75)),
                ),
              ],
            ),
          ),
          const SizedBox(width: 16),
          Container(
            width: 52,
            height: 52,
            decoration: const BoxDecoration(color: Colors.white, shape: BoxShape.circle),
            child: Center(child: Icon(icon, color: SkyTimeColors.violet)),
          ),
        ],
      ),
    );
    if (onTap == null) return content;
    return MouseRegion(
      cursor: SystemMouseCursors.click,
      child: GestureDetector(onTap: onTap, child: content),
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
          final nav = Wrap(
            alignment: WrapAlignment.center,
            spacing: 22,
            runSpacing: 8,
            children: [
              _NavLabel('О ПРОДУКТЕ', onTap: () => _scrollToSection(_aboutKey)),
              _NavLabel('ВОЗМОЖНОСТИ', onTap: () => _scrollToSection(_featuresKey)),
              _NavLabel('ТЕХНОЛОГИИ', onTap: () => _scrollToSection(_techKey)),
              _NavLabel('О НАС', onTap: () => _scrollToSection(_teamKey)),
            ],
          );
          const actions = _AuthActions();

          if (constraints.maxWidth <= 760) {
            return Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [logo, actions],
                ),
                const SizedBox(height: 14),
                Center(child: nav),
              ],
            );
          }
          // Stack + Align центрирует навигацию строго по центру бара
          // независимо от того, сколько места занимают лого слева и
          // кнопки справа.
          return SizedBox(
            height: 44,
            child: Stack(
              alignment: Alignment.center,
              children: [
                const Align(alignment: Alignment.centerLeft, child: logo),
                Align(child: nav),
                const Align(alignment: Alignment.centerRight, child: actions),
              ],
            ),
          );
        },
      ),
    );
  }
}

class _NavLabel extends StatefulWidget {
  const _NavLabel(this.text, {required this.onTap});

  final String text;
  final VoidCallback onTap;

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
      child: GestureDetector(
        onTap: widget.onTap,
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
    return _BentoGrid(
      big: const _BentoBigCard(
        badge: 'ВСЁ В ОДНОМ МЕСТЕ',
        heading: 'ОТ СНИМКА\nДО РЕШЕНИЯ.',
        description:
            'Карта полей, динамика NDVI, аномалии и прогноз урожайности — в '
            'одном дашборде, без ручного разбора спутниковых снимков.',
        decorationIcon: Icons.map_outlined,
      ),
      stat: const _BentoStatCard(
        label: 'ОБНОВЛЕНИЕ ДАННЫХ',
        value: '1–3 дня',
        progress: 0.7,
      ),
      dark: const _BentoDarkCard(
        icon: Icons.show_chart,
        title: 'Восстановление пропусков',
        subtitle: 'Модель закрывает разрывы NDVI из-за облаков',
      ),
      cta: const _BentoCtaCard(
        title: 'ДЕТЕКЦИЯ АНОМАЛИЙ',
        subtitle:
            'Z-score по истории поля — оповещение, когда участок ведёт себя нетипично.',
        icon: Icons.warning_amber_rounded,
      ),
    );
  }
}
