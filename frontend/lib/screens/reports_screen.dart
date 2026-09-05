import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';

import '../data/active_map_controller.dart';
import '../data/auth_repository.dart';
import '../data/vegetation_data_service.dart';
import '../models/anomaly.dart';
import '../models/ndvi_point.dart';
import '../models/ndvi_polygon.dart';
import '../utils/csv_download.dart';
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
/// и последняя зафиксированная аномалия. Выбранные строки (чекбоксы) можно
/// скачать как CSV — открывается в Excel как есть, поэтому отдельный
/// .xlsx-писатель не подключался (лишняя зависимость ради того же результата
/// для пользователя).
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
  final Set<String> _selected = {};
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
        _selected.clear();
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
      final rowIds = rows.map((r) => r.polygon.id).toSet();
      setState(() {
        _rows = rows;
        // Выбор переживает обновление списка только для полигонов, которые
        // в нём всё ещё есть (сменили карту — старый выбор чужой карты
        // потерял бы смысл).
        _selected.retainWhere(rowIds.contains);
        _loading = false;
      });
    } catch (e) {
      setState(() {
        _error = 'Не удалось построить отчёт: $e';
        _loading = false;
      });
    }
  }

  String _csvField(String value) {
    if (value.contains(',') || value.contains('"') || value.contains('\n')) {
      return '"${value.replaceAll('"', '""')}"';
    }
    return value;
  }

  void _exportSelected() {
    final dateFmt = DateFormat('d MMM yyyy', 'ru');
    final selectedRows = _rows.where((r) => _selected.contains(r.polygon.id)).toList();
    final header = ['Участок', 'Культура', 'Площадь (га)', 'Статус', 'Последняя аномалия'];
    final lines = [header.map(_csvField).join(',')];
    for (final r in selectedRows) {
      final anomaly = r.lastAnomaly == null
          ? '—'
          : '${dateFmt.format(r.lastAnomaly!.startDate)} – ${dateFmt.format(r.lastAnomaly!.endDate)}';
      lines.add([
        r.polygon.label,
        r.polygon.cropType,
        r.areaHectares.toStringAsFixed(1),
        statusLabel(r.status),
        anomaly,
      ].map(_csvField).join(','));
    }
    final csv = lines.join('\r\n');

    if (!kIsWeb) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Скачивание файлов поддерживается только в веб-версии')),
      );
      return;
    }
    downloadCsv('skytime_report.csv', csv);
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
          actions: [
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 8),
              child: FilledButton.icon(
                onPressed: _selected.isEmpty ? null : _exportSelected,
                icon: const Icon(Icons.download_outlined, size: 18),
                label: Text('Скачать (${_selected.length})'),
              ),
            ),
          ],
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
                                      selected: _selected.contains(r.polygon.id),
                                      onSelectChanged: (selected) {
                                        setState(() {
                                          if (selected ?? false) {
                                            _selected.add(r.polygon.id);
                                          } else {
                                            _selected.remove(r.polygon.id);
                                          }
                                        });
                                      },
                                      cells: [
                                        // Открыть карточку участка — теперь по тапу на само
                                        // название, а не на всю строку: строка целиком отдана
                                        // под выбор чекбоксом (см. onSelectChanged выше).
                                        DataCell(
                                          InkWell(
                                            onTap: () => context.go('/polygon/${r.polygon.id}'),
                                            child: Text(
                                              r.polygon.label,
                                              style: const TextStyle(
                                                decoration: TextDecoration.underline,
                                              ),
                                            ),
                                          ),
                                        ),
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
