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

/// Корень приложения: краткое приветствие, маленькое интерактивное окошко-
/// превью карты (те же демо-данные, что и на /map) и пояснение того, что
/// есть что. Полноразмерная карта — на /map: так демо видно сразу на
/// экране, без лишних кликов, но остаётся место для текста-объяснения,
/// которого раньше не было (только модальное окно «О проекте»).
class LandingScreen extends StatefulWidget {
  const LandingScreen({super.key, required this.service, required this.auth});

  final VegetationDataService service;
  final AuthRepository auth;

  @override
  State<LandingScreen> createState() => _LandingScreenState();
}

class _LandingScreenState extends State<LandingScreen> {
  List<NdviPolygon> _polygons = [];
  final Map<String, NdviStatus> _latestStatus = {};
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
      for (final p in polygons) {
        final ts = await widget.service.getTimeseries(p.id);
        if (ts.isNotEmpty) _latestStatus[p.id] = ts.last.status;
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
      appBar: AppBar(
        title: SkyTimeLogo(height: 20, color: Theme.of(context).colorScheme.onPrimary),
        actions: [
          IconButton(
            icon: Icon(
              widget.auth.isLoggedIn ? Icons.account_circle : Icons.account_circle_outlined,
            ),
            tooltip: widget.auth.isLoggedIn ? 'Личный кабинет (${widget.auth.email})' : 'Личный кабинет',
            onPressed: () => context.go('/account'),
          ),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.symmetric(vertical: 24),
        children: [
          _Hero(onOpenMap: () => context.go('/map')),
          const SizedBox(height: 28),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 20),
            child: _MapPreview(
              polygons: _polygons,
              latestStatus: _latestStatus,
              loading: _loading,
              onOpenMap: () => context.go('/map'),
              onOpenPolygon: (id) => context.go('/polygon/$id'),
            ),
          ),
          const SizedBox(height: 36),
          const _Description(),
          const SizedBox(height: 24),
        ],
      ),
    );
  }
}

class _Hero extends StatelessWidget {
  const _Hero({required this.onOpenMap});

  final VoidCallback onOpenMap;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          ShaderMask(
            shaderCallback: (rect) => const LinearGradient(
              colors: [SkyTimeColors.teal, SkyTimeColors.lime],
            ).createShader(rect),
            child: const Text(
              'Время видеть больше',
              style: TextStyle(
                color: Colors.white,
                fontSize: 30,
                fontWeight: FontWeight.w800,
                letterSpacing: -0.5,
              ),
            ),
          ),
          const SizedBox(height: 12),
          Text(
            'Мониторинг вегетационной динамики сельхозполей по спутниковым '
            'данным NDVI: восстановление пропусков и детекция аномалий '
            'растительного покрова.',
            style: Theme.of(context).textTheme.bodyLarge,
          ),
          const SizedBox(height: 20),
          Wrap(
            spacing: 12,
            runSpacing: 12,
            children: [
              FilledButton.icon(
                onPressed: onOpenMap,
                icon: const Icon(Icons.map_outlined),
                label: const Text('Открыть карту'),
              ),
              OutlinedButton.icon(
                onPressed: () => GoRouter.of(context).go('/account'),
                icon: const Icon(Icons.person_outline),
                label: const Text('Личный кабинет'),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

/// Маленькое интерактивное окошко-превью: та же карта, те же демо-данные,
/// что и на /map, но в ограниченной по высоте рамке — чтобы сразу на входе
/// было видно, как это выглядит и работает, без перехода на отдельный экран.
class _MapPreview extends StatelessWidget {
  const _MapPreview({
    required this.polygons,
    required this.latestStatus,
    required this.loading,
    required this.onOpenMap,
    required this.onOpenPolygon,
  });

  final List<NdviPolygon> polygons;
  final Map<String, NdviStatus> latestStatus;
  final bool loading;
  final VoidCallback onOpenMap;
  final void Function(String id) onOpenPolygon;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        ClipRRect(
          borderRadius: BorderRadius.circular(16),
          child: Container(
            height: 340,
            decoration: BoxDecoration(border: Border.all(color: Theme.of(context).dividerColor)),
            child: loading
                ? const Center(child: CircularProgressIndicator())
                : Stack(
                    children: [
                      FlutterMap(
                        options: const MapOptions(
                          // Центр — зона реального датасета (южная степная
                          // Россия, ~47°с.ш. ~40°в.д.), а не весь мир: в
                          // маленьком окне так сразу видно демо-полигоны.
                          initialCenter: ll.LatLng(46.2, 40.2),
                          initialZoom: 6.2,
                          minZoom: 3,
                          maxZoom: 14,
                          interactionOptions: InteractionOptions(
                            flags: InteractiveFlag.pinchZoom | InteractiveFlag.drag,
                          ),
                        ),
                        children: [
                          TileLayer(
                            urlTemplate:
                                'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
                            userAgentPackageName: 'com.kosmohack.kosmohack_app',
                            maxNativeZoom: 19,
                          ),
                          MarkerLayer(
                            markers: [
                              for (final p in polygons)
                                Marker(
                                  point: p.centroid,
                                  width: 36,
                                  height: 36,
                                  child: _PreviewPin(
                                    status: latestStatus[p.id] ?? NdviStatus.normal,
                                    onTap: () => onOpenPolygon(p.id),
                                  ),
                                ),
                            ],
                          ),
                        ],
                      ),
                      Positioned(
                        right: 10,
                        bottom: 10,
                        child: FilledButton.tonalIcon(
                          onPressed: onOpenMap,
                          icon: const Icon(Icons.open_in_full, size: 16),
                          label: const Text('На весь экран'),
                        ),
                      ),
                    ],
                  ),
          ),
        ),
        const SizedBox(height: 8),
        Text(
          'Превью на живых демо-данных — двигайте карту, нажимайте на метки '
          'или откройте полную версию.',
          style: Theme.of(context).textTheme.bodySmall,
        ),
      ],
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
            title: 'Аномалии по Z-score',
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
            Text('Шкала Z-score', style: Theme.of(context).textTheme.titleSmall),
            const SizedBox(height: 10),
            _row(NdviStatus.normal, 'Z ≥ −1'),
            _row(NdviStatus.suppression, '−2 ≤ Z < −1'),
            _row(NdviStatus.critical, 'Z < −2'),
          ],
        ),
      ),
    );
  }

  Widget _row(NdviStatus status, String range) {
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
          Text('${statusLabel(status)} ($range)'),
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
