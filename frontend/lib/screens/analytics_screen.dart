import 'package:fl_chart/fl_chart.dart';
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

/// Сводная статистика по своим полигонам: сколько их, общая площадь,
/// разбивка по статусу (Z-score) и по культуре. Только для своих —
/// открытые/найденные автопоиском контуры сюда не входят, так как
/// аналитика имеет смысл именно как «состояние моих полей».
class AnalyticsScreen extends StatefulWidget {
  const AnalyticsScreen({super.key, required this.service, required this.auth, required this.activeMapController});

  final VegetationDataService service;
  final AuthRepository auth;
  final ActiveMapController activeMapController;

  @override
  State<AnalyticsScreen> createState() => _AnalyticsScreenState();
}

class _AnalyticsScreenState extends State<AnalyticsScreen> {
  List<NdviPolygon> _myPolygons = [];
  final Map<String, NdviStatus> _latestStatus = {};
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
    // список молча крутится бесконечно для незалогиненного посетителя.
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
        _error = 'Не удалось загрузить данные: $e';
        _loading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return DashboardShell(
      active: DashboardSection.analytics,
      activeMapController: widget.activeMapController,
      child: Scaffold(
        appBar: AppBar(
          leading: IconButton(
            icon: const Icon(Icons.arrow_back),
            onPressed: () => context.go('/map'),
          ),
          title: const Text('Аналитика'),
        ),
        body: RefreshIndicator(
          onRefresh: _load,
          child: _loading
              ? const Center(child: CircularProgressIndicator())
              : _error != null
                  ? ListView(children: [Padding(padding: const EdgeInsets.all(24), child: Text(_error!))])
                  : _myPolygons.isEmpty
                      ? ListView(
                          children: const [
                            Padding(
                              padding: EdgeInsets.all(24),
                              child: Text('Пока нет своих полигонов — аналитика появится, как только вы нарисуете хотя бы один участок.'),
                            ),
                          ],
                        )
                      : _buildContent(context),
        ),
      ),
    );
  }

  Widget _buildContent(BuildContext context) {
    final totalArea = _myPolygons.fold<double>(0, (sum, p) => sum + polygonAreaHectares(p));
    final byStatus = <NdviStatus, int>{
      NdviStatus.normal: 0,
      NdviStatus.suppression: 0,
      NdviStatus.critical: 0,
    };
    for (final p in _myPolygons) {
      final status = _latestStatus[p.id] ?? NdviStatus.normal;
      byStatus[status] = (byStatus[status] ?? 0) + 1;
    }
    final byCrop = <String, int>{};
    for (final p in _myPolygons) {
      byCrop[p.cropType] = (byCrop[p.cropType] ?? 0) + 1;
    }

    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Wrap(
          spacing: 12,
          runSpacing: 12,
          children: [
            _StatCard(label: 'Своих участков', value: '${_myPolygons.length}'),
            _StatCard(label: 'Общая площадь', value: '${totalArea.toStringAsFixed(1)} га'),
            _StatCard(
              label: 'С отклонениями',
              value: '${byStatus[NdviStatus.suppression]! + byStatus[NdviStatus.critical]!}',
              highlight: byStatus[NdviStatus.suppression]! + byStatus[NdviStatus.critical]! > 0,
            ),
          ],
        ),
        const SizedBox(height: 24),
        Text('Статус по последним данным', style: Theme.of(context).textTheme.titleMedium),
        const SizedBox(height: 12),
        Card(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Row(
              children: [
                SizedBox(
                  width: 140,
                  height: 140,
                  child: PieChart(
                    PieChartData(
                      sectionsSpace: 2,
                      centerSpaceRadius: 32,
                      sections: [
                        for (final status in NdviStatus.values)
                          if (byStatus[status]! > 0)
                            PieChartSectionData(
                              value: byStatus[status]!.toDouble(),
                              color: statusColor(status),
                              title: '${byStatus[status]}',
                              radius: 34,
                              titleStyle: const TextStyle(
                                fontSize: 12,
                                fontWeight: FontWeight.w700,
                                color: Colors.white,
                              ),
                            ),
                      ],
                    ),
                  ),
                ),
                const SizedBox(width: 20),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      for (final status in NdviStatus.values)
                        if (byStatus[status]! > 0) _LegendRow(status: status, count: byStatus[status]!),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ),
        const SizedBox(height: 24),
        Text('По культурам', style: Theme.of(context).textTheme.titleMedium),
        const SizedBox(height: 12),
        Card(
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
            child: Column(
              children: [
                for (final entry in byCrop.entries)
                  ListTile(
                    dense: true,
                    leading: const Icon(Icons.eco_outlined, color: SkyTimeColors.lime),
                    title: Text(entry.key),
                    trailing: Text('${entry.value}'),
                  ),
              ],
            ),
          ),
        ),
      ],
    );
  }
}

class _StatCard extends StatelessWidget {
  const _StatCard({required this.label, required this.value, this.highlight = false});

  final String label;
  final String value;
  final bool highlight;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 180,
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: highlight ? const Color(0xFFE8630A).withValues(alpha: 0.12) : Theme.of(context).cardColor,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: Theme.of(context).dividerColor),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(value, style: const TextStyle(fontSize: 22, fontWeight: FontWeight.w800)),
          const SizedBox(height: 4),
          Text(label, style: TextStyle(fontSize: 12.5, color: Theme.of(context).hintColor)),
        ],
      ),
    );
  }
}

class _LegendRow extends StatelessWidget {
  const _LegendRow({required this.status, required this.count});

  final NdviStatus status;
  final int count;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 3),
      child: Row(
        children: [
          Container(width: 10, height: 10, decoration: BoxDecoration(color: statusColor(status), shape: BoxShape.circle)),
          const SizedBox(width: 8),
          Expanded(child: Text(statusLabel(status), style: const TextStyle(fontSize: 12.5))),
          Text('$count', style: const TextStyle(fontSize: 12.5, fontWeight: FontWeight.w700)),
        ],
      ),
    );
  }
}
