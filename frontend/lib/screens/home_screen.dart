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
import '../widgets/time_slider.dart';

/// Корень приложения. Тёмный hero-блок по референсу дизайна (`style/`,
/// ref1.jpg): крупный заголовок «Время видеть больше», спутниковый снимок,
/// который при наведении (или тапе на тач-устройствах) раскрывается в
/// NDVI-анализ SkyTime — тот же реальный демо-полигон, что и на /map, а не
/// статичная картинка. Ниже — светлый блок с пояснением того, что есть что
/// (без изменений по содержанию, только вход в него теперь другой).
class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key, required this.service, required this.auth});

  final VegetationDataService service;
  final AuthRepository auth;

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  List<NdviPolygon> _polygons = [];
  final Map<String, List<NdviPoint>> _timeseries = {};
  List<DateTime> _dates = [];
  int _dateIndex = 0;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    widget.auth.addListener(_onAuthChanged);
    _load();
  }

  @override
  void dispose() {
    widget.auth.removeListener(_onAuthChanged);
    super.dispose();
  }

  void _onAuthChanged() => setState(() {});

  Future<void> _load() async {
    try {
      final polygons = await widget.service.getPolygons();
      // Параллельно — на реальном бэкенде с десятками полигонов
      // последовательные await-запросы заметно тормозили загрузку.
      final allSeries = await Future.wait(polygons.map((p) => widget.service.getTimeseries(p.id)));
      for (var i = 0; i < polygons.length; i++) {
        _timeseries[polygons[i].id] = allSeries[i];
      }
      final dates = _timeseries.values.expand((l) => l.map((p) => p.date)).toSet().toList()
        ..sort();
      if (!mounted) return;
      setState(() {
        _polygons = polygons;
        _dates = dates;
        _dateIndex = dates.isEmpty ? 0 : dates.length - 1;
        _loading = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() => _loading = false);
    }
  }

  NdviPoint? _pointAt(String polygonId, DateTime date) =>
      nearestPointAt(_timeseries[polygonId], date);

  NdviStatus _statusAt(String id) {
    final date = _dates.isEmpty ? DateTime.now() : _dates[_dateIndex];
    return _pointAt(id, date)?.status ?? NdviStatus.normal;
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: SkyTimeColors.cream,
      body: ListView(
        padding: EdgeInsets.zero,
        children: [
          _HeroSection(
            auth: widget.auth,
            polygons: _polygons,
            statusAt: _statusAt,
            dates: _dates,
            dateIndex: _dateIndex,
            onDateChanged: (i) => setState(() => _dateIndex = i),
            loading: _loading,
            onOpenPolygon: (id) => context.go('/polygon/$id'),
          ),
          const SizedBox(height: 36),
          const _Description(),
          const SizedBox(height: 24),
        ],
      ),
    );
  }
}

/// Тёмная навигационная и hero-секция — на всю ширину экрана, в отличие от
/// остального контента ниже (тот же приём, что на референсе: тёмная
/// «шапка» перетекает в светлый контент).
class _HeroSection extends StatelessWidget {
  const _HeroSection({
    required this.auth,
    required this.polygons,
    required this.statusAt,
    required this.dates,
    required this.dateIndex,
    required this.onDateChanged,
    required this.loading,
    required this.onOpenPolygon,
  });

  final AuthRepository auth;
  final List<NdviPolygon> polygons;
  final NdviStatus Function(String id) statusAt;
  final List<DateTime> dates;
  final int dateIndex;
  final ValueChanged<int> onDateChanged;
  final bool loading;
  final void Function(String id) onOpenPolygon;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      color: SkyTimeColors.navy,
      padding: const EdgeInsets.fromLTRB(20, 20, 20, 32),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          _TopBar(auth: auth),
          const SizedBox(height: 32),
          LayoutBuilder(
            builder: (context, constraints) {
              final wide = constraints.maxWidth > 900;
              final text = _HeroText(onOpenMap: () => context.go('/map'));
              final visual = _HoverRevealPreview(
                polygons: polygons,
                statusAt: statusAt,
                dates: dates,
                dateIndex: dateIndex,
                onDateChanged: onDateChanged,
                loading: loading,
                onOpenPolygon: onOpenPolygon,
              );
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
          const SizedBox(height: 36),
          const _StatStrip(),
        ],
      ),
    );
  }
}

class _TopBar extends StatelessWidget {
  const _TopBar({required this.auth});

  final AuthRepository auth;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        SkyTimeLogo(height: 22, color: SkyTimeColors.cream),
        const Spacer(),
        IconButton(
          icon: Icon(
            auth.isLoggedIn ? Icons.account_circle : Icons.account_circle_outlined,
            color: SkyTimeColors.cream,
          ),
          tooltip: auth.isLoggedIn ? 'Личный кабинет (${auth.email})' : 'Личный кабинет',
          onPressed: () => context.go('/account'),
        ),
      ],
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
          'решения вовремя — восстановление пропусков NDVI и детекция аномалий '
          'растительного покрова.',
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
            OutlinedButton.icon(
              style: OutlinedButton.styleFrom(
                foregroundColor: SkyTimeColors.cream,
                side: BorderSide(color: SkyTimeColors.cream.withValues(alpha: 0.4)),
                padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 14),
              ),
              onPressed: () => GoRouter.of(context).go('/account'),
              icon: const Icon(Icons.person_outline),
              label: const Text('Личный кабинет'),
            ),
          ],
        ),
      ],
    );
  }
}

/// Спутниковый снимок, который при наведении курсора (или тапе — на
/// тач-устройствах наведения не бывает) раскрывается в NDVI-анализ:
/// та же самая карта и те же демо-данные, что на /map, просто в свёрнутом/
/// развёрнутом виде — не отдельная статичная картинка, а честная
/// демонстрация того, что действительно умеет сервис.
class _HoverRevealPreview extends StatefulWidget {
  const _HoverRevealPreview({
    required this.polygons,
    required this.statusAt,
    required this.dates,
    required this.dateIndex,
    required this.onDateChanged,
    required this.loading,
    required this.onOpenPolygon,
  });

  final List<NdviPolygon> polygons;
  final NdviStatus Function(String id) statusAt;
  final List<DateTime> dates;
  final int dateIndex;
  final ValueChanged<int> onDateChanged;
  final bool loading;
  final void Function(String id) onOpenPolygon;

  @override
  State<_HoverRevealPreview> createState() => _HoverRevealPreviewState();
}

class _HoverRevealPreviewState extends State<_HoverRevealPreview> {
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
            // Тач-устройства не шлют onEnter/onExit — тап переключает вручную.
            onTap: () => setState(() => _revealed = !_revealed),
            child: ClipRRect(
              borderRadius: BorderRadius.circular(20),
              child: Container(
                decoration: BoxDecoration(
                  border: Border.all(color: SkyTimeColors.cream.withValues(alpha: 0.15)),
                ),
                child: widget.loading
                    ? const SizedBox(height: 340, child: Center(child: CircularProgressIndicator()))
                    : SizedBox(
                        height: 340,
                        child: Stack(
                          children: [
                            FlutterMap(
                              options: const MapOptions(
                                // Центр — зона реального датасета (южная
                                // степная Россия, ~46°с.ш. ~40°в.д.).
                                initialCenter: ll.LatLng(46.2, 40.2),
                                initialZoom: 6.2,
                                minZoom: 3,
                                maxZoom: 14,
                                interactionOptions: InteractionOptions(
                                  flags: InteractiveFlag.pinchZoom |
                                      InteractiveFlag.drag |
                                      InteractiveFlag.scrollWheelZoom |
                                      InteractiveFlag.doubleTapZoom,
                                ),
                              ),
                              children: [
                                TileLayer(
                                  urlTemplate:
                                      'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
                                  userAgentPackageName: 'com.kosmohack.kosmohack_app',
                                  maxNativeZoom: 19,
                                ),
                                AnimatedOpacity(
                                  duration: const Duration(milliseconds: 260),
                                  opacity: _revealed ? 1 : 0,
                                  child: PolygonLayer(
                                    polygons: [
                                      for (final p in widget.polygons)
                                        Polygon(
                                          points: p.points,
                                          color: statusColor(widget.statusAt(p.id)).withValues(alpha: 0.45),
                                          borderColor: statusColor(widget.statusAt(p.id)),
                                          borderStrokeWidth: 2.5,
                                        ),
                                    ],
                                  ),
                                ),
                                AnimatedOpacity(
                                  duration: const Duration(milliseconds: 260),
                                  opacity: _revealed ? 1 : 0,
                                  child: MarkerLayer(
                                    markers: [
                                      for (final p in widget.polygons)
                                        Marker(
                                          point: p.centroid,
                                          width: 36,
                                          height: 36,
                                          child: _PreviewPin(
                                            status: widget.statusAt(p.id),
                                            onTap: () => widget.onOpenPolygon(p.id),
                                          ),
                                        ),
                                    ],
                                  ),
                                ),
                              ],
                            ),
                            Positioned(
                              left: 12,
                              top: 12,
                              child: AnimatedOpacity(
                                duration: const Duration(milliseconds: 200),
                                opacity: _revealed ? 0 : 1,
                                child: const _Badge(text: 'СПУТНИК'),
                              ),
                            ),
                            Positioned(
                              left: 12,
                              top: 12,
                              child: AnimatedOpacity(
                                duration: const Duration(milliseconds: 200),
                                opacity: _revealed ? 1 : 0,
                                child: const _Badge(text: 'АНАЛИЗ SKYTIME', color: SkyTimeColors.teal),
                              ),
                            ),
                          ],
                        ),
                      ),
              ),
            ),
          ),
        ),
        const SizedBox(height: 10),
        Text(
          widget.loading
              ? 'Загрузка демо-данных…'
              : 'Наведите курсор на снимок (на телефоне — коснитесь), чтобы увидеть '
                  'анализ SkyTime: тот же участок, размеченный по состоянию посевов.',
          style: TextStyle(color: SkyTimeColors.cream.withValues(alpha: 0.65), fontSize: 13),
        ),
        if (!widget.loading && widget.dates.isNotEmpty) ...[
          const SizedBox(height: 10),
          ClipRRect(
            borderRadius: BorderRadius.circular(12),
            child: TimeSlider(dates: widget.dates, index: widget.dateIndex, onChanged: widget.onDateChanged),
          ),
        ],
      ],
    );
  }
}

class _Badge extends StatelessWidget {
  const _Badge({required this.text, this.color = SkyTimeColors.navy});

  final String text;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.85),
        borderRadius: BorderRadius.circular(20),
      ),
      child: Text(
        text,
        style: const TextStyle(color: Colors.white, fontSize: 11, fontWeight: FontWeight.w700, letterSpacing: 0.4),
      ),
    );
  }
}

class _PreviewPin extends StatelessWidget {
  const _PreviewPin({required this.status, required this.onTap});

  final NdviStatus status;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(18),
      child: Icon(
        status == NdviStatus.normal ? Icons.location_on : Icons.warning_rounded,
        color: statusColor(status),
        size: 28,
        shadows: const [Shadow(blurRadius: 4, color: Colors.black45)],
      ),
    );
  }
}

/// Нижняя плашка hero-секции — по референсу (Sentinel-2 / обновление /
/// облачная обработка / защита данных), только с реальными фактами проекта.
class _StatStrip extends StatelessWidget {
  const _StatStrip();

  @override
  Widget build(BuildContext context) {
    return Wrap(
      spacing: 28,
      runSpacing: 18,
      children: const [
        _StatItem(icon: Icons.satellite_alt_outlined, title: 'SENTINEL-2', subtitle: '10 м / пиксель'),
        _StatItem(icon: Icons.update, title: 'КАЖДЫЕ 1–3 ДНЯ', subtitle: 'обновление данных'),
        _StatItem(icon: Icons.cloud_outlined, title: 'ВОССТАНОВЛЕНИЕ ПРОПУСКОВ', subtitle: 'модель поверх спутника'),
        _StatItem(icon: Icons.shield_outlined, title: 'ВАШИ ДАННЫЕ', subtitle: 'видны только вам'),
      ],
    );
  }
}

class _StatItem extends StatelessWidget {
  const _StatItem({required this.icon, required this.title, required this.subtitle});

  final IconData icon;
  final String title;
  final String subtitle;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: 200,
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, color: SkyTimeColors.lime, size: 20),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: const TextStyle(color: Colors.white, fontSize: 12, fontWeight: FontWeight.w700, letterSpacing: 0.2),
                ),
                const SizedBox(height: 2),
                Text(
                  subtitle,
                  style: TextStyle(color: SkyTimeColors.cream.withValues(alpha: 0.6), fontSize: 11),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _Description extends StatelessWidget {
  const _Description();

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Что есть что', style: Theme.of(context).textTheme.headlineSmall),
          const SizedBox(height: 16),
          const _FeatureRow(
            icon: Icons.map_outlined,
            title: 'Карта полей',
            text: 'Выберите готовый контур поля или нарисуйте свой прямо на карте.',
          ),
          const _FeatureRow(
            icon: Icons.show_chart,
            title: 'Временной ряд NDVI',
            text: 'График показывает и реальные наблюдения, и восстановленные значения '
                'там, где данных не было — отдельно.',
          ),
          const _FeatureRow(
            icon: Icons.warning_amber_rounded,
            title: 'Детекция аномалий',
            text: 'Три уровня — штатное развитие, угнетение биомассы, критическая '
                'аномалия — с объяснением вероятной причины.',
          ),
          const _FeatureRow(
            icon: Icons.travel_explore,
            title: 'Работа с любым регионом',
            text: 'Автопоиск контуров в новой области, управление своим набором полей: '
                'добавить, отредактировать, удалить.',
          ),
          const SizedBox(height: 24),
          _ZScoreLegendCard(),
          const SizedBox(height: 24),
          Card(
            color: Theme.of(context).colorScheme.surfaceContainerHighest,
            child: const Padding(
              padding: EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('Данные', style: TextStyle(fontWeight: FontWeight.w600)),
                  SizedBox(height: 6),
                  Text(
                    'Спутник: Sentinel-2, ~10 м/пиксель. Регион демо-данных: Ростовская '
                    'область, Краснодарский и Ставропольский край. Культуры: озимая '
                    'пшеница, подсолнечник, пастбища/зерновые.',
                  ),
                  SizedBox(height: 6),
                  Text(
                    'Карта работает на тестовых данных без регистрации. Аккаунт нужен '
                    'только для сохранения своих полигонов на реальном сервере.',
                    style: TextStyle(fontSize: 12),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _ZScoreLegendCard extends StatelessWidget {
  const _ZScoreLegendCard();

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Статус участка', style: Theme.of(context).textTheme.titleSmall),
            const SizedBox(height: 10),
            _row(NdviStatus.normal),
            _row(NdviStatus.suppression),
            _row(NdviStatus.critical),
          ],
        ),
      ),
    );
  }

  Widget _row(NdviStatus status) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        children: [
          Container(
            width: 12,
            height: 12,
            decoration: BoxDecoration(color: statusColor(status), shape: BoxShape.circle),
          ),
          const SizedBox(width: 8),
          Text(statusLabel(status)),
        ],
      ),
    );
  }
}

class _FeatureRow extends StatelessWidget {
  const _FeatureRow({required this.icon, required this.title, required this.text});

  final IconData icon;
  final String title;
  final String text;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 14),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, size: 22, color: SkyTimeColors.teal),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(title, style: Theme.of(context).textTheme.titleSmall),
                Text(text, style: Theme.of(context).textTheme.bodyMedium),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
