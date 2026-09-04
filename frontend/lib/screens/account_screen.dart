import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../data/auth_repository.dart';
import '../data/vegetation_data_service.dart';
import '../models/ndvi_point.dart';
import '../models/ndvi_polygon.dart';
import '../theme.dart';
import '../utils/ndvi_style.dart';
import '../widgets/dashboard_shell.dart';

/// Личный кабинет: кто вошёл, свои полигоны, быстрые действия
/// («создать полигон», «посмотреть все на карте»). «Свои» полигоны —
/// это `isCustom == true`: в моке они все принадлежат текущей сессии,
/// на реальном бэкенде — те, что создал текущий пользователь (владелец
/// проверяется на сервере при изменении/удалении).
class AccountScreen extends StatefulWidget {
  const AccountScreen({super.key, required this.service, required this.auth});

  final VegetationDataService service;
  final AuthRepository auth;

  @override
  State<AccountScreen> createState() => _AccountScreenState();
}

class _AccountScreenState extends State<AccountScreen> {
  List<NdviPolygon> _myPolygons = [];
  final Map<String, NdviStatus> _latestStatus = {};
  bool _loading = true;
  String? _error;

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
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final all = await widget.service.getPolygons();
      final mine = all.where((p) => p.isCustom).toList();
      // Параллельно, не по одному — см. аналогичный урок в map_screen.dart.
      final series = await Future.wait(mine.map((p) => widget.service.getTimeseries(p.id)));
      for (var i = 0; i < mine.length; i++) {
        if (series[i].isNotEmpty) _latestStatus[mine[i].id] = series[i].last.status;
      }
      setState(() {
        _myPolygons = mine;
        _loading = false;
      });
    } catch (e) {
      setState(() {
        _error = 'Не удалось загрузить полигоны: $e';
        _loading = false;
      });
    }
  }

  /// Площадь по формуле шнурков в приближении «плоской земли» — точность
  /// достаточна для небольших нарисованных участков (не для картографии),
  /// метры на градус долготы взяты для широты центроида полигона.
  double _areaHectares(NdviPolygon polygon) {
    final points = polygon.points;
    if (points.length < 3) return 0;
    const metersPerDegLat = 111320.0;
    final centroidLat = points.map((p) => p.latitude).reduce((a, b) => a + b) / points.length;
    final metersPerDegLon = metersPerDegLat * math.cos(centroidLat * math.pi / 180);
    final xy = points.map((p) => (p.longitude * metersPerDegLon, p.latitude * metersPerDegLat)).toList();
    double sum = 0;
    for (var i = 0; i < xy.length; i++) {
      final (x1, y1) = xy[i];
      final (x2, y2) = xy[(i + 1) % xy.length];
      sum += x1 * y2 - x2 * y1;
    }
    return (sum.abs() / 2) / 10000; // м² -> га
  }

  static const _accentColors = [
    SkyTimeColors.lime,
    SkyTimeColors.teal,
    SkyTimeColors.violet,
    SkyTimeColors.pink,
  ];

  @override
  Widget build(BuildContext context) {
    final loggedIn = widget.auth.isLoggedIn;
    return DashboardShell(
      active: DashboardSection.account,
      child: Scaffold(
      appBar: AppBar(
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          onPressed: () => context.go('/map'),
        ),
        title: const Text('Личный кабинет'),
      ),
      body: RefreshIndicator(
        onRefresh: _load,
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            Card(
              child: ListTile(
                leading: CircleAvatar(
                  backgroundColor: SkyTimeColors.teal,
                  child: Icon(
                    loggedIn ? Icons.person : Icons.person_outline,
                    color: Colors.white,
                  ),
                ),
                title: Text(loggedIn ? (widget.auth.email ?? '') : 'Вы не вошли'),
                subtitle: Text(
                  loggedIn
                      ? 'Аккаунт подтверждён'
                      : 'Войдите, чтобы сохранять свои полигоны на сервере',
                ),
                trailing: loggedIn
                    ? TextButton(onPressed: widget.auth.logout, child: const Text('Выйти'))
                    : TextButton(
                        onPressed: () => context.go('/login'),
                        child: const Text('Войти'),
                      ),
              ),
            ),
            const SizedBox(height: 16),
            Wrap(
              spacing: 12,
              runSpacing: 12,
              children: [
                FilledButton.icon(
                  onPressed: () {
                    if (!widget.auth.isLoggedIn) {
                      context.go('/login');
                      return;
                    }
                    context.go('/map?draw=1');
                  },
                  icon: const Icon(Icons.add_location_alt_outlined),
                  // Зачёркнуто, пока не вошли — функция доступна только
                  // авторизованным, но кнопка кликабельна и ведёт на /login.
                  label: Text(
                    'Создать полигон',
                    style: loggedIn
                        ? null
                        : const TextStyle(decoration: TextDecoration.lineThrough),
                  ),
                ),
                OutlinedButton.icon(
                  onPressed: () => context.go('/map'),
                  icon: const Icon(Icons.map_outlined),
                  label: const Text('Посмотреть все на карте'),
                ),
              ],
            ),
            const SizedBox(height: 24),
            Text('Мои полигоны', style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 8),
            if (_loading)
              const Padding(
                padding: EdgeInsets.all(24),
                child: Center(child: CircularProgressIndicator()),
              )
            else if (_error != null)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 12),
                child: Text(_error!),
              )
            else if (_myPolygons.isEmpty)
              const Padding(
                padding: EdgeInsets.symmetric(vertical: 12),
                child: Text('Пока нет своих полигонов — нарисуйте первый на карте.'),
              )
            else
              for (var i = 0; i < _myPolygons.length; i++)
                _PolygonCard(
                  polygon: _myPolygons[i],
                  areaHectares: _areaHectares(_myPolygons[i]),
                  status: _latestStatus[_myPolygons[i].id],
                  accent: _accentColors[i % _accentColors.length],
                  onTap: () => context.go('/polygon/${_myPolygons[i].id}'),
                ),
          ],
        ),
      ),
      ),
    );
  }
}

/// Карточка участка по референсу макета (`style/SkyTime Map & Account.dc.html`):
/// цветная полоска слева, площадь, статус в виде «таблетки». Цвет
/// полоски — просто визуальный акцент по кругу цветов бренда (не несёт
/// смысла), цвет самой таблетки статуса — настоящий Z-score-статус.
class _PolygonCard extends StatelessWidget {
  const _PolygonCard({
    required this.polygon,
    required this.areaHectares,
    required this.status,
    required this.accent,
    required this.onTap,
  });

  final NdviPolygon polygon;
  final double areaHectares;
  final NdviStatus? status;
  final Color accent;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final effectiveStatus = status ?? NdviStatus.normal;
    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
          child: Row(
            children: [
              Container(width: 4, height: 32, decoration: BoxDecoration(
                color: accent, borderRadius: BorderRadius.circular(2))),
              const SizedBox(width: 14),
              Expanded(
                flex: 3,
                child: Text(polygon.label,
                    style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 13.5),
                    overflow: TextOverflow.ellipsis),
              ),
              Expanded(
                flex: 2,
                child: Text('${areaHectares.toStringAsFixed(1)} га',
                    style: TextStyle(fontSize: 12.5, color: Theme.of(context).hintColor)),
              ),
              Expanded(
                flex: 2,
                child: Text(polygon.cropType,
                    style: TextStyle(fontSize: 12.5, color: Theme.of(context).hintColor),
                    overflow: TextOverflow.ellipsis),
              ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
                decoration: BoxDecoration(
                  color: statusColor(effectiveStatus).withValues(alpha: 0.15),
                  borderRadius: BorderRadius.circular(999),
                ),
                child: Text(
                  statusLabel(effectiveStatus),
                  style: TextStyle(
                    fontSize: 10.5,
                    fontWeight: FontWeight.w700,
                    color: statusColor(effectiveStatus),
                  ),
                ),
              ),
              const SizedBox(width: 8),
              const Icon(Icons.chevron_right, size: 18),
            ],
          ),
        ),
      ),
    );
  }
}
