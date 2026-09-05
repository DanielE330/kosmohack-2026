import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';

import '../data/active_map_controller.dart';
import '../data/auth_repository.dart';
import '../data/vegetation_data_service.dart';
import '../models/anomaly.dart';
import '../models/ndvi_point.dart';
import '../utils/ndvi_style.dart';
import '../widgets/dashboard_shell.dart';

/// Лента аномалий по своим полигонам — «уведомления» в терминах ТЗ
/// (детекция отклонений уже считается на бэкенде/моке, здесь только
/// показываем результат в удобном списке, отсортированном по дате).
class NotificationsScreen extends StatefulWidget {
  const NotificationsScreen({super.key, required this.service, required this.auth, required this.activeMapController});

  final VegetationDataService service;
  final AuthRepository auth;
  final ActiveMapController activeMapController;

  @override
  State<NotificationsScreen> createState() => _NotificationsScreenState();
}

class _NotificationsScreenState extends State<NotificationsScreen> {
  List<Anomaly> _anomalies = [];
  final Map<String, String> _polygonLabels = {};
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    widget.auth.addListener(_load);
    widget.activeMapController.addListener(_load);
    _load();
  }

  @override
  void dispose() {
    widget.auth.removeListener(_load);
    widget.activeMapController.removeListener(_load);
    super.dispose();
  }

  Future<void> _load() async {
    // Без входа своих полигонов не бывает — не ходим в сеть вообще, иначе
    // лента молча крутится бесконечно для незалогиненного посетителя.
    if (!widget.auth.isLoggedIn) {
      setState(() {
        _anomalies = [];
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
      final polygons = await widget.service.getPolygons(mapId: widget.activeMapController.active?.id);
      final mine = polygons.where((p) => p.isCustom).toList();
      final mineIds = mine.map((p) => p.id).toSet();
      for (final p in mine) {
        _polygonLabels[p.id] = p.label;
      }
      // Бэкенд/мок уже поддерживают запрос без polygonId — отдают все
      // аномалии сразу, дальше просто фильтруем по своим id на клиенте.
      final all = await widget.service.getAnomalies();
      final mineAnomalies = all.where((a) => mineIds.contains(a.polygonId)).toList()
        ..sort((a, b) => b.startDate.compareTo(a.startDate));
      setState(() {
        _anomalies = mineAnomalies;
        _loading = false;
      });
    } catch (e) {
      setState(() {
        _error = 'Не удалось загрузить уведомления: $e';
        _loading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final dateFmt = DateFormat('d MMM yyyy', 'ru');
    return DashboardShell(
      active: DashboardSection.notifications,
      activeMapController: widget.activeMapController,
      child: Scaffold(
        appBar: AppBar(
          leading: IconButton(
            icon: const Icon(Icons.arrow_back),
            onPressed: () => context.go('/map'),
          ),
          title: const Text('Уведомления'),
        ),
        body: RefreshIndicator(
          onRefresh: _load,
          child: _loading
              ? const Center(child: CircularProgressIndicator())
              : ListView(
                  padding: const EdgeInsets.all(16),
                  children: [
                    if (_error != null)
                      Padding(padding: const EdgeInsets.symmetric(vertical: 12), child: Text(_error!))
                    else if (_anomalies.isEmpty)
                      const Padding(
                        padding: EdgeInsets.symmetric(vertical: 12),
                        child: Text('Отклонений по вашим участкам не обнаружено — всё в штатном режиме.'),
                      )
                    else
                      for (final a in _anomalies)
                        _AnomalyTile(
                          anomaly: a,
                          polygonLabel: _polygonLabels[a.polygonId] ?? a.polygonId,
                          dateFmt: dateFmt,
                          onTap: () => context.go('/polygon/${a.polygonId}'),
                        ),
                  ],
                ),
        ),
      ),
    );
  }
}

class _AnomalyTile extends StatelessWidget {
  const _AnomalyTile({
    required this.anomaly,
    required this.polygonLabel,
    required this.dateFmt,
    required this.onTap,
  });

  final Anomaly anomaly;
  final String polygonLabel;
  final DateFormat dateFmt;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final color = statusColor(anomaly.severity);
    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Icon(
                anomaly.severity == NdviStatus.critical ? Icons.error_outline : Icons.warning_amber_outlined,
                color: color,
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(polygonLabel, style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 13.5)),
                    const SizedBox(height: 2),
                    Text(
                      '${dateFmt.format(anomaly.startDate)} — ${dateFmt.format(anomaly.endDate)}',
                      style: TextStyle(fontSize: 12, color: Theme.of(context).hintColor),
                    ),
                    if (anomaly.explanation.isNotEmpty) ...[
                      const SizedBox(height: 6),
                      Text(anomaly.explanation, style: const TextStyle(fontSize: 12.5)),
                    ],
                  ],
                ),
              ),
              const SizedBox(width: 8),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
                decoration: BoxDecoration(color: color.withValues(alpha: 0.15), borderRadius: BorderRadius.circular(999)),
                child: Text(
                  statusLabel(anomaly.severity),
                  style: TextStyle(fontSize: 10.5, fontWeight: FontWeight.w700, color: color),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
