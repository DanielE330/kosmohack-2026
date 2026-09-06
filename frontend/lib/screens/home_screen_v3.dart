import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:go_router/go_router.dart';
import 'package:latlong2/latlong.dart' as ll;

import '../data/auth_repository.dart';
import '../data/vegetation_data_service.dart';
import '../models/ndvi_point.dart';
import '../models/ndvi_polygon.dart';
import '../theme.dart';
import '../utils/ndvi_style.dart';
import '../widgets/skytime_logo.dart';

/// Вариант 3 для сравнения: тот же живой снимок, что в варианте 1, но
/// вместо наведения — перетаскиваемый вертикальный разделитель
/// «до/после» (привычный паттерн сравнения изображений), работает
/// одинаково и на десктопе, и на телефоне — не нужен fallback на тап.
class HomeScreenV3 extends StatefulWidget {
  const HomeScreenV3({super.key, required this.service, required this.auth});

  final VegetationDataService service;
  final AuthRepository auth;

  @override
  State<HomeScreenV3> createState() => _HomeScreenV3State();
}

class _HomeScreenV3State extends State<HomeScreenV3> {
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

  NdviStatus _statusAt(String id) {
    final series = _timeseries[id];
    if (series == null || series.isEmpty) return NdviStatus.normal;
    return series.last.status;
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
                    final visual = _DragCompareMap(polygons: _polygons, statusAt: _statusAt, loading: _loading);
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
              'Вариант 3 (для сравнения на :2032): тяните разделитель — не наведение, а перетаскивание.',
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

/// Одна и та же карта в двух копиях друг над другом: нижняя — чистый
/// спутник, верхняя (с NDVI-раскраской) обрезается по X перетаскиваемым
/// разделителем через ClipRect, как в привычных виджетах сравнения фото.
class _DragCompareMap extends StatefulWidget {
  const _DragCompareMap({required this.polygons, required this.statusAt, required this.loading});

  final List<NdviPolygon> polygons;
  final NdviStatus Function(String id) statusAt;
  final bool loading;

  @override
  State<_DragCompareMap> createState() => _DragCompareMapState();
}

class _DragCompareMapState extends State<_DragCompareMap> {
  double _split = 0.5; // 0..1, доля ширины, занятая "анализом" слева

  Widget _buildMap({required bool analysis}) {
    return FlutterMap(
      options: const MapOptions(
        initialCenter: ll.LatLng(46.2, 40.2),
        initialZoom: 6.2,
        minZoom: 3,
        maxZoom: 14,
        interactionOptions: InteractionOptions(flags: InteractiveFlag.none),
      ),
      children: [
        TileLayer(
          urlTemplate: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
          userAgentPackageName: 'com.kosmohack.kosmohack_app',
          maxNativeZoom: 19,
        ),
        if (analysis)
          PolygonLayer(
            polygons: [
              for (final p in widget.polygons)
                Polygon(
                  points: p.points,
                  color: statusColor(widget.statusAt(p.id)).withValues(alpha: 0.5),
                  borderColor: statusColor(widget.statusAt(p.id)),
                  borderStrokeWidth: 2.5,
                ),
            ],
          ),
      ],
    );
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        ClipRRect(
          borderRadius: BorderRadius.circular(20),
          child: SizedBox(
            height: 340,
            child: widget.loading
                ? const ColoredBox(color: SkyTimeColors.navy, child: Center(child: CircularProgressIndicator(color: Colors.white)))
                : LayoutBuilder(
                    builder: (context, constraints) {
                      final width = constraints.maxWidth;
                      return GestureDetector(
                        onHorizontalDragUpdate: (details) {
                          setState(() {
                            _split = (_split + details.delta.dx / width).clamp(0.0, 1.0);
                          });
                        },
                        child: Stack(
                          fit: StackFit.expand,
                          children: [
                            _buildMap(analysis: false),
                            ClipRect(
                              clipper: _LeftClipper(_split),
                              child: _buildMap(analysis: true),
                            ),
                            Positioned(
                              left: width * _split - 1,
                              top: 0,
                              bottom: 0,
                              child: Container(width: 2, color: Colors.white),
                            ),
                            Positioned(
                              left: (width * _split - 18).clamp(0.0, width - 36),
                              top: 340 / 2 - 18,
                              child: Container(
                                width: 36,
                                height: 36,
                                decoration: BoxDecoration(
                                  color: Colors.white,
                                  shape: BoxShape.circle,
                                  boxShadow: [BoxShadow(color: Colors.black.withValues(alpha: 0.3), blurRadius: 6)],
                                ),
                                child: const Icon(Icons.drag_indicator, color: SkyTimeColors.navy, size: 20),
                              ),
                            ),
                            const Positioned(left: 12, top: 12, child: _Chip(text: 'АНАЛИЗ SKYTIME', color: SkyTimeColors.teal)),
                            const Positioned(right: 12, top: 12, child: _Chip(text: 'СПУТНИК')),
                          ],
                        ),
                      );
                    },
                  ),
          ),
        ),
        const SizedBox(height: 10),
        Text(
          'Потяните разделитель влево-вправо, чтобы сравнить спутниковый снимок '
          'с анализом SkyTime.',
          style: TextStyle(color: SkyTimeColors.cream.withValues(alpha: 0.65), fontSize: 13),
        ),
      ],
    );
  }
}

class _LeftClipper extends CustomClipper<Rect> {
  _LeftClipper(this.fraction);

  final double fraction;

  @override
  Rect getClip(Size size) => Rect.fromLTWH(0, 0, size.width * fraction, size.height);

  @override
  bool shouldReclip(covariant _LeftClipper oldClipper) => oldClipper.fraction != fraction;
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
