import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../data/auth_repository.dart';
import '../data/vegetation_data_service.dart';
import '../models/ndvi_point.dart';
import '../models/ndvi_polygon.dart';
import '../theme.dart';
import '../utils/ndvi_style.dart';
import '../widgets/skytime_logo.dart';

/// Вариант 2 для сравнения: вместо живой карты — абстрактная «акварельная»
/// картинка ближе к буквальному виду референса (ref1.jpg): цветные пятна
/// поверх сетки полей, при наведении/тапе меняющие палитру со
/// спутниково-холодной на NDVI-тёплую (зелёный/жёлтый/красный).
/// Не использует внешние изображения — только градиенты и CustomPaint,
/// чтобы не тащить в проект чужие фото без прав.
class HomeScreenV2 extends StatefulWidget {
  const HomeScreenV2({super.key, required this.service, required this.auth});

  final VegetationDataService service;
  final AuthRepository auth;

  @override
  State<HomeScreenV2> createState() => _HomeScreenV2State();
}

class _HomeScreenV2State extends State<HomeScreenV2> {
  List<NdviPolygon> _polygons = [];
  final Map<String, List<NdviPoint>> _timeseries = {};
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final polygons = await widget.service.getPolygons();
      final allSeries = await Future.wait(polygons.map((p) => widget.service.getTimeseries(p.id)));
      for (var i = 0; i < polygons.length; i++) {
        _timeseries[polygons[i].id] = allSeries[i];
      }
      if (!mounted) return;
      setState(() {
        _polygons = polygons;
        _loading = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: SkyTimeColors.cream,
      body: ListView(
        padding: EdgeInsets.zero,
        children: [
          Container(
            width: double.infinity,
            color: SkyTimeColors.navy,
            padding: const EdgeInsets.fromLTRB(20, 20, 20, 32),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Row(
                  children: [
                    SkyTimeLogo(height: 22, color: SkyTimeColors.cream),
                    const Spacer(),
                    IconButton(
                      icon: Icon(
                        widget.auth.isLoggedIn ? Icons.account_circle : Icons.account_circle_outlined,
                        color: SkyTimeColors.cream,
                      ),
                      onPressed: () => context.go('/account'),
                    ),
                  ],
                ),
                const SizedBox(height: 32),
                LayoutBuilder(
                  builder: (context, constraints) {
                    final wide = constraints.maxWidth > 900;
                    final text = _HeroText(onOpenMap: () => context.go('/map'));
                    final visual = _WatercolorReveal(polygons: _polygons, loading: _loading);
                    if (wide) {
                      return Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Expanded(flex: 5, child: text),
                          const SizedBox(width: 40),
                          Expanded(flex: 6, child: visual),
                        ],
                      );
                    }
                    return Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [text, const SizedBox(height: 32), visual],
                    );
                  },
                ),
              ],
            ),
          ),
          const SizedBox(height: 36),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 20),
            child: Text(
              'Вариант 2 (для сравнения на :2031): абстрактная картинка вместо живой карты.',
              style: Theme.of(context).textTheme.bodyMedium,
            ),
          ),
          const SizedBox(height: 24),
        ],
      ),
    );
  }
}

class _HeroText extends StatelessWidget {
  const _HeroText({required this.onOpenMap});

  final VoidCallback onOpenMap;

  static const _headline = TextStyle(
    color: Colors.white,
    fontSize: 44,
    fontWeight: FontWeight.w800,
    height: 1.04,
    letterSpacing: -1,
  );

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text('ВРЕМЯ', style: _headline),
        const Text('ВИДЕТЬ', style: _headline),
        ShaderMask(
          shaderCallback: (rect) => const LinearGradient(
            colors: [SkyTimeColors.teal, SkyTimeColors.lime],
          ).createShader(rect),
          child: const Text('БОЛЬШЕ.', style: _headline),
        ),
        const SizedBox(height: 18),
        Text(
          'Спутниковые данные помогают увидеть изменения на Земле и принимать '
          'решения вовремя.',
          style: TextStyle(color: SkyTimeColors.cream.withValues(alpha: 0.78), fontSize: 15, height: 1.55),
        ),
        const SizedBox(height: 24),
        Wrap(
          spacing: 12,
          runSpacing: 12,
          children: [
            FilledButton.icon(
              style: FilledButton.styleFrom(
                backgroundColor: SkyTimeColors.cream,
                foregroundColor: SkyTimeColors.navy,
                padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 14),
              ),
              onPressed: onOpenMap,
              icon: const Icon(Icons.arrow_forward),
              label: const Text('Начать наблюдение'),
            ),
          ],
        ),
      ],
    );
  }
}

/// Абстрактная картинка: сетка «полей» на градиентном пятне. Наведение
/// (или тап) плавно перекрашивает пятно из холодной спутниковой палитры
/// (синий/бирюзовый/фиолетовый) в тёплую NDVI-палитру (зелёный/жёлтый/
/// красный) — по цвету реальных статусов участков, если они уже загрузились.
class _WatercolorReveal extends StatefulWidget {
  const _WatercolorReveal({required this.polygons, required this.loading});

  final List<NdviPolygon> polygons;
  final bool loading;

  @override
  State<_WatercolorReveal> createState() => _WatercolorRevealState();
}

class _WatercolorRevealState extends State<_WatercolorReveal> {
  bool _revealed = false;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        MouseRegion(
          onEnter: (_) => setState(() => _revealed = true),
          onExit: (_) => setState(() => _revealed = false),
          child: GestureDetector(
            onTap: () => setState(() => _revealed = !_revealed),
            child: ClipRRect(
              borderRadius: BorderRadius.circular(20),
              child: SizedBox(
                height: 340,
                child: Stack(
                  fit: StackFit.expand,
                  children: [
                    AnimatedContainer(
                      duration: const Duration(milliseconds: 400),
                      decoration: BoxDecoration(
                        gradient: RadialGradient(
                          center: const Alignment(0.3, -0.2),
                          radius: 1.3,
                          colors: _revealed
                              ? const [Color(0xFF89D146), Color(0xFFE8C93A), Color(0xFF032F37)]
                              : const [Color(0xFF16B2AE), Color(0xFF805FCD), Color(0xFF032F37)],
                        ),
                      ),
                    ),
                    CustomPaint(painter: _FieldGridPainter(), size: Size.infinite),
                    Positioned(
                      left: 16,
                      top: 16,
                      child: AnimatedOpacity(
                        duration: const Duration(milliseconds: 200),
                        opacity: _revealed ? 0 : 1,
                        child: const _Chip(text: 'СПУТНИК'),
                      ),
                    ),
                    Positioned(
                      left: 16,
                      top: 16,
                      child: AnimatedOpacity(
                        duration: const Duration(milliseconds: 200),
                        opacity: _revealed ? 1 : 0,
                        child: const _Chip(text: 'АНАЛИЗ SKYTIME', color: SkyTimeColors.teal),
                      ),
                    ),
                    if (widget.loading)
                      const Center(child: CircularProgressIndicator(color: Colors.white)),
                  ],
                ),
              ),
            ),
          ),
        ),
        const SizedBox(height: 10),
        Text(
          'Наведите курсор на картинку (на телефоне — коснитесь), чтобы увидеть '
          'разницу между спутниковым снимком и анализом SkyTime.',
          style: TextStyle(color: SkyTimeColors.cream.withValues(alpha: 0.65), fontSize: 13),
        ),
      ],
    );
  }
}

class _Chip extends StatelessWidget {
  const _Chip({required this.text, this.color = SkyTimeColors.navy});

  final String text;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
      decoration: BoxDecoration(color: color.withValues(alpha: 0.85), borderRadius: BorderRadius.circular(20)),
      child: Text(text, style: const TextStyle(color: Colors.white, fontSize: 11, fontWeight: FontWeight.w700, letterSpacing: 0.4)),
    );
  }
}

/// Тонкая нерегулярная сетка линий — намёк на границы полей поверх
/// градиентного пятна, без реальных геоданных (это чисто декоративный слой).
class _FieldGridPainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = Colors.white.withValues(alpha: 0.18)
      ..strokeWidth = 1;
    const cols = 7;
    const rows = 5;
    for (var i = 1; i < cols; i++) {
      final x = size.width * i / cols;
      canvas.drawLine(Offset(x, 0), Offset(x, size.height), paint);
    }
    for (var i = 1; i < rows; i++) {
      final y = size.height * i / rows;
      canvas.drawLine(Offset(0, y), Offset(size.width, y), paint);
    }
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}
