import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';

import '../data/active_map_controller.dart';
import '../data/auth_repository.dart';
import '../data/vegetation_data_service.dart';
import '../models/anomaly.dart';
import '../models/ndvi_point.dart';
import '../models/ndvi_polygon.dart';
import '../utils/geo.dart';
import '../utils/ndvi_style.dart';
import '../widgets/dashboard_shell.dart';

class _Row {
  _Row(this.polygon, this.areaHectares, this.status, this.lastAnomaly);
  final NdviPolygon polygon;
  final double areaHectares;
  final NdviStatus status;
  final Anomaly? lastAnomaly;
}

/// Табличная сводка по своим участкам — площадь, культура, текущий статус
/// и последняя зафиксированная аномалия. Экспорт в файл сознательно не
/// реализован (не требуется ТЗ для MVP) — таблица служит именно как отчёт
/// «на экране», который можно посмотреть или сфотографировать при демо.
class ReportsScreen extends StatefulWidget {
  const ReportsScreen({super.key, required this.service, required this.auth, required this.activeMapController});

  final VegetationDataService service;
  final AuthRepository auth;
  final ActiveMapController activeMapController;

  @override
  State<ReportsScreen> createState() => _ReportsScreenState();
}

class _ReportsScreenState extends State<ReportsScreen> {
  List<_Row> _rows = [];
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
    // таблица молча крутится бесконечно для незалогиненного посетителя.
    if (!widget.auth.isLoggedIn) {
      setState(() {
        _rows = [];
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
      final series = await Future.wait(mine.map((p) => widget.service.getTimeseries(p.id)));
      final allAnomalies = await widget.service.getAnomalies();

      final rows = <_Row>[];
      for (var i = 0; i < mine.length; i++) {
        final status = series[i].isNotEmpty ? series[i].last.status : NdviStatus.normal;
        final own = allAnomalies.where((a) => a.polygonId == mine[i].id).toList()
          ..sort((a, b) => b.startDate.compareTo(a.startDate));
        rows.add(_Row(mine[i], polygonAreaHectares(mine[i]), status, own.isEmpty ? null : own.first));
      }
      setState(() {
        _rows = rows;
        _loading = false;
      });
    } catch (e) {
      setState(() {
        _error = 'Не удалось построить отчёт: $e';
        _loading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final dateFmt = DateFormat('d MMM yyyy', 'ru');
    return DashboardShell(
      active: DashboardSection.reports,
      activeMapController: widget.activeMapController,
      child: Scaffold(
        appBar: AppBar(
          leading: IconButton(
            icon: const Icon(Icons.arrow_back),
            onPressed: () => context.go('/map'),
          ),
          title: const Text('Отчёты'),
        ),
        body: RefreshIndicator(
          onRefresh: _load,
          child: _loading
              ? const Center(child: CircularProgressIndicator())
              : _error != null
                  ? ListView(children: [Padding(padding: const EdgeInsets.all(24), child: Text(_error!))])
                  : _rows.isEmpty
                      ? ListView(
                          children: const [
                            Padding(
                              padding: EdgeInsets.all(24),
                              child: Text('Пока нет своих участков — отчёт появится, как только вы нарисуете хотя бы один.'),
                            ),
                          ],
                        )
                      : ListView(
                          padding: const EdgeInsets.all(16),
                          children: [
                            SingleChildScrollView(
                              scrollDirection: Axis.horizontal,
                              child: DataTable(
                                columns: const [
                                  DataColumn(label: Text('Участок')),
                                  DataColumn(label: Text('Культура')),
                                  DataColumn(label: Text('Площадь')),
                                  DataColumn(label: Text('Статус')),
                                  DataColumn(label: Text('Последняя аномалия')),
                                ],
                                rows: [
                                  for (final r in _rows)
                                    DataRow(
                                      onSelectChanged: (_) => context.go('/polygon/${r.polygon.id}'),
                                      cells: [
                                        DataCell(Text(r.polygon.label)),
                                        DataCell(Text(r.polygon.cropType)),
                                        DataCell(Text('${r.areaHectares.toStringAsFixed(1)} га')),
                                        DataCell(Container(
                                          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                                          decoration: BoxDecoration(
                                            color: statusColor(r.status).withValues(alpha: 0.15),
                                            borderRadius: BorderRadius.circular(999),
                                          ),
                                          child: Text(
                                            statusLabel(r.status),
                                            style: TextStyle(fontSize: 10.5, fontWeight: FontWeight.w700, color: statusColor(r.status)),
                                          ),
                                        )),
                                        DataCell(Text(
                                          r.lastAnomaly == null
                                              ? '—'
                                              : '${dateFmt.format(r.lastAnomaly!.startDate)} – ${dateFmt.format(r.lastAnomaly!.endDate)}',
                                        )),
                                      ],
                                    ),
                                ],
                              ),
                            ),
                          ],
                        ),
        ),
      ),
    );
  }
}
