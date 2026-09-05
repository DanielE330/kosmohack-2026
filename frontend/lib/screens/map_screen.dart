import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:go_router/go_router.dart';
import 'package:latlong2/latlong.dart' as ll;

import '../data/active_map_controller.dart';
import '../data/auth_repository.dart';
import '../data/reverse_geocode.dart';
import '../data/vegetation_data_service.dart';
import '../models/map_info.dart';
import '../models/ndvi_point.dart';
import '../models/ndvi_polygon.dart';
import '../route_observer.dart';
import '../utils/ndvi_style.dart';
import '../widgets/about_dialog.dart';
import '../widgets/dashboard_shell.dart';
import '../widgets/skytime_logo.dart';
import '../widgets/time_slider.dart';

class MapScreen extends StatefulWidget {
  const MapScreen({
    super.key,
    required this.service,
    required this.auth,
    required this.activeMapController,
    this.startDrawing = false,
  });

  final VegetationDataService service;
  final AuthRepository auth;
  final ActiveMapController activeMapController;

  /// Личный кабинет ведёт сразу в режим рисования (кнопка «Создать
  /// полигон» на /account) — на самой карте отдельной кнопки «Нарисовать
  /// полигон» больше нет.
  final bool startDrawing;

  @override
  State<MapScreen> createState() => _MapScreenState();
}

class _MapScreenState extends State<MapScreen> with RouteAware {
  List<NdviPolygon> _polygons = [];
  // По умолчанию на карте видно только то, что создал сам пользователь —
  // готовые контуры соревнования (не is_custom) не должны сразу
  // захламлять вид на живом бэкенде. "Найти контуры" — осознанное
  // действие, поэтому найденные им полигоны тоже открываются на карте.
  final Set<String> _revealedIds = {};
  List<NdviPolygon> get _visiblePolygons =>
      _polygons.where((p) => p.isCustom || _revealedIds.contains(p.id)).toList();
  final Map<String, List<NdviPoint>> _timeseries = {};
  List<DateTime> _dates = [];
  int _dateIndex = 0;
  bool _loading = true;
  String? _error;

  bool _drawing = false;
  final List<ll.LatLng> _draftPoints = [];
  final List<ll.LatLng> _redoPoints = [];
  bool _submittingDraft = false;

  final MapController _mapController = MapController();
  bool _searchingRegion = false;
  bool _consumedStartDrawing = false;

  @override
  void initState() {
    super.initState();
    widget.auth.addListener(_onAuthChanged);
    // Смена активной карты в переключателе (сайдбар) должна перезагрузить
    // именно полигоны, а не просто перерисовать экран со старым списком —
    // у каждой карты свой независимый набор участков.
    widget.activeMapController.addListener(_load);
    _load();
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    routeObserver.subscribe(this, ModalRoute.of(context) as PageRoute);
  }

  @override
  void dispose() {
    routeObserver.unsubscribe(this);
    widget.auth.removeListener(_onAuthChanged);
    widget.activeMapController.removeListener(_load);
    _mapController.dispose();
    super.dispose();
  }

  void _onAuthChanged() => setState(() {});

  /// Стандартный `RouteAware` — вызывается, когда этот экран снова
  /// становится верхним в стеке после `pop`, независимо от того, кто его
  /// вызвал: внутриприложенческая стрелка «назад» или браузерная кнопка
  /// (см. комментарий у `routeObserver` в app.dart).
  @override
  void didPopNext() => _load();

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final polygons = await widget.service.getPolygons(mapId: widget.activeMapController.active?.id);
      // Параллельно, а не по одному — на реальном бэкенде с десятками
      // полигонов последовательные await-запросы давали заметную задержку
      // загрузки карты (каждый timeseries — отдельный HTTP-запрос).
      final allSeries = await Future.wait(polygons.map((p) => widget.service.getTimeseries(p.id)));
      for (var i = 0; i < polygons.length; i++) {
        _timeseries[polygons[i].id] = allSeries[i];
      }
      final dates = _timeseries.values.expand((l) => l.map((p) => p.date)).toSet().toList()
        ..sort();
      setState(() {
        _polygons = polygons;
        _dates = dates;
        _dateIndex = dates.isEmpty ? 0 : dates.length - 1;
        _loading = false;
      });
      // Личный кабинет может привести сюда сразу с намерением рисовать
      // (`?draw=1`) — включаем режим рисования один раз при первой
      // загрузке. Есть и прямой способ — свой FAB прямо на карте.
      if (widget.startDrawing && !_consumedStartDrawing) {
        _consumedStartDrawing = true;
        if (_needsLogin) {
          _promptLogin();
        } else if (mounted && _canDraw) {
          setState(() {
            _drawing = true;
            _draftPoints.clear();
          });
        }
      }
    } catch (e) {
      setState(() {
        _error = 'Не удалось загрузить данные: $e';
        _loading = false;
      });
    }
  }

  NdviPoint? _pointAt(String polygonId, DateTime date) =>
      nearestPointAt(_timeseries[polygonId], date);

  /// Раньше проверялось только для реального бэкенда — теперь личный
  /// кабинет предполагает, что создавать/менять свои полигоны можно
  /// только войдя, независимо от мока/реального API.
  bool get _needsLogin => !widget.auth.isLoggedIn;

  /// Viewer на расшаренной карте видит полигоны, но не может рисовать —
  /// та же проверка роли, что и на бэкенде (см. `app/api/routes/polygons.py`,
  /// `_require_edit_access`), только заранее прячет кнопку, а не даёт
  /// нарваться на 403 после рисования.
  bool get _canDraw {
    final active = widget.activeMapController.active;
    return active == null || mapRoleCanEdit(active.role);
  }

  void _promptLogin() {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: const Text('Чтобы рисовать и удалять свои полигоны, нужно войти'),
        action: SnackBarAction(label: 'Войти', onPressed: () => context.go('/login')),
      ),
    );
  }

  /// Отменяет уже идущее рисование.
  void _cancelDrawing() {
    setState(() {
      _drawing = false;
      _draftPoints.clear();
      _redoPoints.clear();
    });
  }

  void _onMapTap(ll.LatLng point) {
    if (!_drawing) return;
    setState(() {
      _draftPoints.add(point);
      // Новая вершина отменяет ветку «вперёд» — как в любом стандартном
      // undo/redo (иначе Ctrl+Y вернул бы точку, которая уже не имеет
      // отношения к текущей форме полигона).
      _redoPoints.clear();
    });
  }

  void _undoPoint() {
    if (_draftPoints.isEmpty) return;
    setState(() => _redoPoints.add(_draftPoints.removeLast()));
  }

  void _redoPoint() {
    if (_redoPoints.isEmpty) return;
    setState(() => _draftPoints.add(_redoPoints.removeLast()));
  }

  void _openPolygon(NdviPolygon polygon) {
    context.go('/polygon/${polygon.id}');
  }

  /// Спрашивает название нового полигона перед сохранением — иначе
  /// пользователь получал бы безликое авто-имя вроде «Мой полигон N» и не
  /// мог бы отличить свои участки друг от друга в личном кабинете.
  Future<String?> _askPolygonName() async {
    final controller = TextEditingController();
    return showDialog<String>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Название полигона'),
        content: TextField(
          controller: controller,
          autofocus: true,
          decoration: const InputDecoration(labelText: 'Например, «Северное поле»'),
          onSubmitted: (v) => Navigator.of(context).pop(v.trim()),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(),
            child: const Text('Отмена'),
          ),
          FilledButton(
            onPressed: () => Navigator.of(context).pop(controller.text.trim()),
            child: const Text('Сохранить'),
          ),
        ],
      ),
    );
  }

  Future<void> _finishDrawing() async {
    if (_draftPoints.length < 3) return;
    final label = await _askPolygonName();
    if (label == null) return; // отменено в диалоге
    if (!mounted) return;
    setState(() => _submittingDraft = true);
    try {
      final polygon = await widget.service.submitCustomPolygon(
        _draftPoints,
        label: label,
        mapId: widget.activeMapController.active?.id,
      );
      if (!mounted) return;
      setState(() {
        _drawing = false;
        _draftPoints.clear();
        _redoPoints.clear();
        _submittingDraft = false;
      });
      _openPolygon(polygon);
    } catch (e) {
      if (!mounted) return;
      setState(() => _submittingDraft = false);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Не удалось сохранить полигон: $e')),
      );
    }
  }

  /// Автопоиск доступных сельхозконтуров в границах текущего вида карты —
  /// критерий «Управление полигонами» требует это отдельно от ручного
  /// рисования (см. tasks/backend.md, GET /polygons?region=).
  Future<void> _searchRegion() async {
    final bounds = _mapController.camera.visibleBounds;
    setState(() => _searchingRegion = true);
    try {
      final found = await widget.service.findPolygonsInRegion(
        minLat: bounds.south,
        minLon: bounds.west,
        maxLat: bounds.north,
        maxLon: bounds.east,
      );
      final foundSeries = await Future.wait(found.map((p) => widget.service.getTimeseries(p.id)));
      for (var i = 0; i < found.length; i++) {
        _timeseries[found[i].id] = foundSeries[i];
      }
      final knownIds = _polygons.map((p) => p.id).toSet();
      if (!mounted) return;
      setState(() {
        _polygons = [..._polygons, ...found.where((p) => !knownIds.contains(p.id))];
        _revealedIds.addAll(found.map((p) => p.id));
        _searchingRegion = false;
      });
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(found.isEmpty
              ? 'В этой области контуры не найдены'
              : 'Найдено контуров: ${found.length}'),
        ),
      );
    } catch (e) {
      if (!mounted) return;
      setState(() => _searchingRegion = false);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Не удалось выполнить поиск: $e')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return DashboardShell(
      active: DashboardSection.map,
      activeMapController: widget.activeMapController,
      child: Scaffold(
      appBar: AppBar(
        leading: IconButton(
          icon: const Icon(Icons.info_outline),
          tooltip: 'О проекте',
          onPressed: () => showSkyTimeAboutDialog(context),
        ),
        title: SkyTimeLogo(height: 20, color: Theme.of(context).colorScheme.onPrimary),
        actions: [
          IconButton(
            icon: _searchingRegion
                ? const SizedBox(
                    width: 20,
                    height: 20,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Icon(Icons.travel_explore),
            tooltip: 'Найти контуры полей в этой области',
            onPressed: (_loading || _searchingRegion) ? null : _searchRegion,
          ),
          IconButton(
            icon: const Icon(Icons.refresh),
            tooltip: 'Обновить',
            onPressed: _loading ? null : _load,
          ),
          IconButton(
            icon: Icon(widget.auth.isLoggedIn ? Icons.account_circle : Icons.account_circle_outlined),
            tooltip: widget.auth.isLoggedIn ? 'Личный кабинет (${widget.auth.email})' : 'Личный кабинет',
            onPressed: () => context.go('/account'),
          ),
          // На узких экранах сайдбар дашборда скрыт (см. DashboardShell) —
          // без этого меню разделы аналитики/уведомлений/отчётов/настроек
          // были бы недостижимы на телефоне.
          if (MediaQuery.sizeOf(context).width < 900)
            PopupMenuButton<String>(
              icon: const Icon(Icons.more_vert),
              tooltip: 'Ещё',
              onSelected: (route) => context.go(route),
              itemBuilder: (context) => const [
                PopupMenuItem(value: '/analytics', child: Text('Аналитика')),
                PopupMenuItem(value: '/notifications', child: Text('Уведомления')),
                PopupMenuItem(value: '/reports', child: Text('Отчёты')),
                PopupMenuItem(value: '/settings', child: Text('Настройки')),
              ],
            ),
        ],
      ),
      // Ctrl+Z/Ctrl+Y во время рисования — отменить/вернуть последнюю
      // поставленную точку полигона (стандартное сочетание, ожидаемое от
      // любого рисовалки).
      body: Focus(
        autofocus: true,
        onKeyEvent: (node, event) {
          if (!_drawing || event is! KeyDownEvent) return KeyEventResult.ignored;
          // isMetaPressed — на Mac для undo/redo принято Cmd, а не Ctrl.
          final ctrl = HardwareKeyboard.instance.isControlPressed ||
              HardwareKeyboard.instance.isMetaPressed;
          if (ctrl && event.logicalKey == LogicalKeyboardKey.keyZ) {
            _undoPoint();
            return KeyEventResult.handled;
          }
          if (ctrl && event.logicalKey == LogicalKeyboardKey.keyY) {
            _redoPoint();
            return KeyEventResult.handled;
          }
          return KeyEventResult.ignored;
        },
        child: _buildBody(),
      ),
      ),
    );
  }

  Widget _buildBody() {
    if (_loading) {
      return const Center(child: CircularProgressIndicator());
    }
    if (_error != null) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(_error!, textAlign: TextAlign.center),
              const SizedBox(height: 12),
              FilledButton(onPressed: _load, child: const Text('Повторить')),
            ],
          ),
        ),
      );
    }

    final selectedDate = _dates.isEmpty ? DateTime.now() : _dates[_dateIndex];

    return Column(
      children: [
        if (_drawing)
          Container(
            width: double.infinity,
            color: Theme.of(context).colorScheme.primaryContainer,
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
            child: Text(
              'Режим рисования: тапните по карте, чтобы добавить вершины '
              'полигона (нужно минимум 3).',
              style: Theme.of(context).textTheme.bodySmall,
            ),
          ),
        Expanded(
          child: Stack(
            children: [
              FlutterMap(
                mapController: _mapController,
                options: MapOptions(
                  initialCenter: const ll.LatLng(10, 20),
                  initialZoom: 2.2,
                  minZoom: 2,
                  maxZoom: 16,
                  onTap: (tapPosition, point) => _onMapTap(point),
                ),
                children: [
                  // Только спутник — Esri World Imagery (бесплатный, без
                  // ключа, легален для встраивания как XYZ-тайлы). Yandex-
                  // тайлы сюда нельзя: их спутник отдаётся только через
                  // собственный JS Maps API, а не как обычные XYZ-тайлы —
                  // хотлинк их внутренних тайл-серверов нарушает условия
                  // использования и ненадёжен (могут заблокировать без
                  // предупреждения).
                  TileLayer(
                    urlTemplate:
                        'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
                    userAgentPackageName: 'com.kosmohack.kosmohack_app',
                    maxNativeZoom: 19,
                  ),
                  PolygonLayer(
                    polygons: [
                      for (final p in _visiblePolygons)
                        if (_pointAt(p.id, selectedDate) != null)
                          Polygon(
                            points: p.points,
                            color: statusColor(_pointAt(p.id, selectedDate)!.status)
                                .withValues(alpha: 0.45),
                            borderColor: statusColor(_pointAt(p.id, selectedDate)!.status),
                            borderStrokeWidth: 2,
                          ),
                      if (_draftPoints.length >= 2)
                        Polygon(
                          points: _draftPoints,
                          color: Colors.blue.withValues(alpha: 0.25),
                          borderColor: Colors.blue,
                          borderStrokeWidth: 2,
                        ),
                    ],
                  ),
                  MarkerLayer(
                    markers: [
                      for (final p in _visiblePolygons)
                        Marker(
                          point: p.centroid,
                          width: 44,
                          height: 44,
                          child: _PolygonPin(
                            polygon: p,
                            status: _pointAt(p.id, selectedDate)?.status,
                            onTap: () => _openPolygon(p),
                          ),
                        ),
                      for (final pt in _draftPoints)
                        Marker(
                          point: pt,
                          width: 12,
                          height: 12,
                          child: const DecoratedBox(
                            decoration: BoxDecoration(
                              color: Colors.blue,
                              shape: BoxShape.circle,
                            ),
                          ),
                        ),
                    ],
                  ),
                ],
              ),
              // Обязательная атрибуция тайлов Esri — как обычный текст, без
              // кнопок и всплывающих панелей. Слева, а не справа — иначе
              // перекрывалась бы с FAB рисования в том же углу.
              const Positioned(
                left: 4,
                bottom: 4,
                child: IgnorePointer(
                  child: DecoratedBox(
                    decoration: BoxDecoration(color: Color(0x99FFFFFF)),
                    child: Padding(
                      padding: EdgeInsets.symmetric(horizontal: 4, vertical: 1),
                      child: Text('Esri World Imagery', style: TextStyle(fontSize: 10)),
                    ),
                  ),
                ),
              ),
              if (_submittingDraft)
                const Positioned.fill(
                  child: ColoredBox(
                    color: Colors.black26,
                    child: Center(child: CircularProgressIndicator()),
                  ),
                ),
              const Positioned(left: 12, top: 12, child: _Legend()),
              // Раньше был Scaffold.floatingActionButton — по умолчанию
              // прилипает к нижнему краю экрана и перекрывал TimeSlider
              // под ним. Теперь позиционируем сами, внутри области карты,
              // так что кнопка всегда оказывается над временной шкалой,
              // а не поверх неё.
              if (!_loading && _error == null && _drawing)
                Positioned(
                  right: 16,
                  bottom: 16,
                  child: FloatingActionButton.extended(
                    onPressed: _draftPoints.length >= 3 ? _finishDrawing : _cancelDrawing,
                    icon: Icon(_draftPoints.length >= 3 ? Icons.check : Icons.close),
                    label: Text(_draftPoints.length >= 3
                        ? 'Готово (${_draftPoints.length})'
                        : 'Отменить рисование'),
                  ),
                ),
              // Прямой запуск рисования с самой карты — раньше сюда можно
              // было попасть только через кнопку в личном кабинете
              // (`/map?draw=1`), теперь есть и прямой путь, без лишнего
              // перехода на другой экран.
              if (!_loading && _error == null && !_drawing && _canDraw)
                Positioned(
                  right: 16,
                  bottom: 16,
                  child: FloatingActionButton.extended(
                    onPressed: () {
                      if (_needsLogin) {
                        _promptLogin();
                        return;
                      }
                      setState(() {
                        _drawing = true;
                        _draftPoints.clear();
                        _redoPoints.clear();
                      });
                    },
                    icon: const Icon(Icons.add_location_alt_outlined),
                    label: const Text('Создать полигон'),
                  ),
                ),
            ],
          ),
        ),
        if (_visiblePolygons.isNotEmpty)
          _PolygonCarousel(
            polygons: _visiblePolygons,
            statusAt: (id) => _pointAt(id, selectedDate)?.status,
            onTap: (p) => _mapController.move(p.centroid, _mapController.camera.zoom),
            onOpenStats: _openPolygon,
          ),
        TimeSlider(
          dates: _dates,
          index: _dateIndex,
          onChanged: (i) => setState(() => _dateIndex = i),
        ),
      ],
    );
  }
}

/// Горизонтальная карусель участков над временной шкалой — набор карточек
/// свой у каждой карты (см. `mapId` в `_load()`): переключились на другую
/// карту в сайдбаре — здесь окажутся её собственные полигоны, а не общий
/// список; нарисовали новый полигон — карусель обновится сама вместе с
/// `_polygons` при следующей загрузке. Один тап — карта перецентровывается
/// на выбранный участок (быстрый способ найти поле среди многих, не
/// выцеливая мелкую метку на карте); двойной тап — открывает карточку
/// участка со статистикой (тот же переход, что и по метке на карте).
class _PolygonCarousel extends StatelessWidget {
  const _PolygonCarousel({
    required this.polygons,
    required this.statusAt,
    required this.onTap,
    required this.onOpenStats,
  });

  final List<NdviPolygon> polygons;
  final NdviStatus? Function(String id) statusAt;
  final void Function(NdviPolygon) onTap;
  final void Function(NdviPolygon) onOpenStats;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 60,
      child: ListView.separated(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        itemCount: polygons.length,
        separatorBuilder: (_, _) => const SizedBox(width: 4),
        itemBuilder: (context, i) {
          final p = polygons[i];
          final status = statusAt(p.id) ?? NdviStatus.normal;
          return InkWell(
            borderRadius: BorderRadius.circular(10),
            onTap: () => onTap(p),
            onDoubleTap: () => onOpenStats(p),
            child: Container(
              width: 140,
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 6),
              child: Row(
                children: [
                  Container(
                    width: 8,
                    height: 8,
                    decoration: BoxDecoration(color: statusColor(status), shape: BoxShape.circle),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          p.label,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: const TextStyle(fontSize: 12.5, fontWeight: FontWeight.w600),
                        ),
                        _LocationLine(polygon: p),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          );
        },
      ),
    );
  }
}

/// Страна/субъект/район под названием участка — подгружаются обратным
/// геокодированием по центроиду (см. `data/reverse_geocode.dart`), пока не
/// пришёл ответ или если геокодирование не удалось — культура как fallback,
/// так карточка никогда не остаётся пустой.
class _LocationLine extends StatelessWidget {
  const _LocationLine({required this.polygon});

  final NdviPolygon polygon;

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<ReverseGeocodeResult>(
      future: reverseGeocode(polygon.centroid),
      builder: (context, snapshot) {
        final label = (snapshot.data != null && !snapshot.data!.isEmpty)
            ? snapshot.data!.shortLabel
            : polygon.cropType;
        return Text(
          label,
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
          style: TextStyle(fontSize: 10.5, color: Theme.of(context).hintColor),
        );
      },
    );
  }
}

class _PolygonPin extends StatelessWidget {
  const _PolygonPin({
    required this.polygon,
    required this.status,
    required this.onTap,
  });

  final NdviPolygon polygon;
  final NdviStatus? status;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final s = status ?? NdviStatus.normal;
    return Tooltip(
      message: '${polygon.label} (${polygon.cropType})',
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(22),
        child: Icon(
          s == NdviStatus.normal ? Icons.location_on : Icons.warning_rounded,
          color: statusColor(s),
          size: 34,
          shadows: const [Shadow(blurRadius: 4, color: Colors.black45)],
        ),
      ),
    );
  }
}

class _Legend extends StatelessWidget {
  const _Legend();

  @override
  Widget build(BuildContext context) {
    return Card(
      color: Theme.of(context).colorScheme.surface.withValues(alpha: 0.92),
      child: Padding(
        padding: const EdgeInsets.all(10),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: [
            Text('Статус участка', style: Theme.of(context).textTheme.labelLarge),
            const SizedBox(height: 4),
            _legendRow(NdviStatus.normal),
            _legendRow(NdviStatus.suppression),
            _legendRow(NdviStatus.critical),
          ],
        ),
      ),
    );
  }

  Widget _legendRow(NdviStatus status) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 2),
      child: Row(
        children: [
          Container(
            width: 12,
            height: 12,
            decoration:
                BoxDecoration(color: statusColor(status), shape: BoxShape.circle),
          ),
          const SizedBox(width: 6),
          Text(statusLabel(status), style: const TextStyle(fontSize: 11)),
        ],
      ),
    );
  }
}
