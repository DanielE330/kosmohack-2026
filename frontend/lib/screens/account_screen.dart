import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../data/active_map_controller.dart';
import '../data/auth_repository.dart';
import '../data/vegetation_data_service.dart';
import '../models/ndvi_point.dart';
import '../models/ndvi_polygon.dart';
import '../theme.dart';
import '../utils/geo.dart';
import '../utils/ndvi_style.dart';
import '../widgets/dashboard_shell.dart';

/// Свои полигоны + быстрые действия («создать полигон», «посмотреть все на
/// карте»). Кто вошёл/выход — в Настройках, не здесь. «Свои» полигоны —
/// это `isCustom == true`: в моке они все принадлежат текущей сессии,
/// на реальном бэкенде — те, что создал текущий пользователь (владелец
/// проверяется на сервере при изменении/удалении).
class AccountScreen extends StatefulWidget {
  const AccountScreen({super.key, required this.service, required this.auth, required this.activeMapController});

  final VegetationDataService service;
  final AuthRepository auth;
  final ActiveMapController activeMapController;

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
    // У каждой карты свой независимый набор полигонов — переключение в
    // селекторе карт должно перезагрузить список, а не оставлять старый.
    widget.activeMapController.addListener(_load);
    _load();
  }

  @override
  void dispose() {
    widget.auth.removeListener(_onAuthChanged);
    widget.activeMapController.removeListener(_load);
    super.dispose();
  }

  void _onAuthChanged() => _load();

  Future<void> _load() async {
    // Без входа своих полигонов не бывает (создание требует логина) —
    // не ходим в сеть вообще, иначе список молча крутится бесконечно.
    if (!widget.auth.isLoggedIn) {
      setState(() {
        _myPolygons = [];
        _loading = false;
        _error = null;
      });
      return;
    }
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final all = await widget.service.getPolygons(mapId: widget.activeMapController.active?.id);
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
      activeMapController: widget.activeMapController,
      child: Scaffold(
      appBar: AppBar(
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          onPressed: () => context.go('/map'),
        ),
        title: const Text('Мои участки'),
      ),
      body: RefreshIndicator(
        onRefresh: _load,
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            if (!loggedIn)
              Card(
                child: ListTile(
                  contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                  leading: const CircleAvatar(
                    backgroundColor: SkyTimeColors.teal,
                    child: Icon(Icons.person_outline, color: Colors.white),
                  ),
                  title: const Text('Вы не вошли'),
                  subtitle: const Text('Войдите, чтобы сохранять свои полигоны на сервере'),
                  trailing: FilledButton(
                    onPressed: () => context.go('/login'),
                    child: const Text('Войти'),
                  ),
                ),
              ),
            // Кто вошёл/выход — теперь в Настройках, здесь только участки
            // (см. запрос пользователя перенести аккаунт из "Участков").
            if (!loggedIn) const SizedBox(height: 16),
            // Сводка по своим участкам — те же данные, что уже загружены
            // для списка, просто собранные в одну строку: открывая кабинет,
            // хочется сразу увидеть «сколько всего и что горит».
            if (loggedIn && !_loading && _myPolygons.isNotEmpty) ...[
              _SummaryStrip(polygons: _myPolygons, statuses: _latestStatus),
              const SizedBox(height: 20),
            ],
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
            const SizedBox(height: 28),
            Text('Мои полигоны', style: Theme.of(context).textTheme.titleLarge),
            const SizedBox(height: 12),
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
                  areaHectares: polygonAreaHectares(_myPolygons[i]),
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

/// Сводка «сколько участков / сколько гектаров / сколько не в норме».
/// Считается по уже загруженным данным — дополнительных запросов не
/// делает.
class _SummaryStrip extends StatelessWidget {
  const _SummaryStrip({required this.polygons, required this.statuses});

  final List<NdviPolygon> polygons;
  final Map<String, NdviStatus> statuses;

  @override
  Widget build(BuildContext context) {
    final totalHectares =
        polygons.fold<double>(0, (sum, p) => sum + polygonAreaHectares(p));
    final attention = polygons
        .where((p) => (statuses[p.id] ?? NdviStatus.normal) != NdviStatus.normal)
        .length;

    return LayoutBuilder(
      builder: (context, constraints) {
        // На узком экране три плитки в ряд сжимаются до нечитаемого —
        // там они переносятся в столбик (Wrap с полной шириной).
        final tileWidth = constraints.maxWidth < 520
            ? constraints.maxWidth
            : (constraints.maxWidth - 24) / 3;
        return Wrap(
          spacing: 12,
          runSpacing: 12,
          children: [
            SizedBox(
              width: tileWidth,
              child: _SummaryTile(
                icon: Icons.crop_square_outlined,
                label: 'Участков',
                value: '${polygons.length}',
                accent: SkyTimeColors.teal,
              ),
            ),
            SizedBox(
              width: tileWidth,
              child: _SummaryTile(
                icon: Icons.straighten_outlined,
                label: 'Общая площадь',
                value: '${totalHectares.toStringAsFixed(1)} га',
                accent: SkyTimeColors.lime,
              ),
            ),
            SizedBox(
              width: tileWidth,
              child: _SummaryTile(
                icon: Icons.warning_amber_outlined,
                label: 'Требуют внимания',
                value: '$attention',
                accent: attention > 0 ? statusColor(NdviStatus.suppression) : SkyTimeColors.violet,
              ),
            ),
          ],
        );
      },
    );
  }
}

class _SummaryTile extends StatelessWidget {
  const _SummaryTile({
    required this.icon,
    required this.label,
    required this.value,
    required this.accent,
  });

  final IconData icon;
  final String label;
  final String value;
  final Color accent;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
      decoration: BoxDecoration(
        color: theme.cardColor,
        borderRadius: BorderRadius.circular(SkyTimeRadii.large),
        border: Border.all(color: theme.colorScheme.outlineVariant),
      ),
      child: Row(
        children: [
          Container(
            width: 36,
            height: 36,
            decoration: BoxDecoration(
              color: accent.withValues(alpha: 0.14),
              borderRadius: BorderRadius.circular(SkyTimeRadii.small),
            ),
            child: Icon(icon, size: 18, color: accent),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(label, style: theme.textTheme.labelMedium),
                const SizedBox(height: 2),
                Text(
                  value,
                  style: theme.textTheme.titleLarge?.copyWith(fontSize: 20),
                  overflow: TextOverflow.ellipsis,
                ),
              ],
            ),
          ),
        ],
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
        hoverColor: SkyTimeColors.teal.withValues(alpha: 0.06),
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 14),
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
