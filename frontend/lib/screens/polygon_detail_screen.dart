import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';

import '../data/vegetation_data_service.dart';
import '../models/anomaly.dart';
import '../models/ndvi_point.dart';
import '../models/ndvi_polygon.dart';
import '../utils/ndvi_style.dart';
import '../widgets/ndvi_chart.dart';

class PolygonDetailScreen extends StatefulWidget {
  const PolygonDetailScreen({
    super.key,
    required this.service,
    required this.polygon,
  });

  final VegetationDataService service;
  final NdviPolygon polygon;

  @override
  State<PolygonDetailScreen> createState() => _PolygonDetailScreenState();
}

class _PolygonDetailScreenState extends State<PolygonDetailScreen> {
  List<NdviPoint> _points = [];
  List<Anomaly> _anomalies = [];
  bool _loading = true;
  bool _deleting = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final points = await widget.service.getTimeseries(widget.polygon.id);
      final anomalies =
          await widget.service.getAnomalies(polygonId: widget.polygon.id);
      setState(() {
        _points = points;
        _anomalies = anomalies..sort((a, b) => b.startDate.compareTo(a.startDate));
        _loading = false;
      });
    } catch (e) {
      setState(() {
        _error = 'Не удалось загрузить данные: $e';
        _loading = false;
      });
    }
  }

  /// Критерий «Управление полигонами» требует не только добавлять, но и
  /// удалять выбранные участки — см. tasks/backend.md (DELETE /polygons/{id}).
  Future<void> _confirmDelete() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Удалить полигон?'),
        content: Text('«${widget.polygon.label}» будет убран из набора. '
            'Действие необратимо.'),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: const Text('Отмена'),
          ),
          FilledButton.tonal(
            onPressed: () => Navigator.of(context).pop(true),
            child: const Text('Удалить'),
          ),
        ],
      ),
    );
    if (confirmed != true) return;

    setState(() => _deleting = true);
    try {
      await widget.service.deletePolygon(widget.polygon.id);
      if (!mounted) return;
      // Возврат назад: MapScreen сам перезапросит список полигонов после
      // того, как этот push разрешится (см. _openPolygon в map_screen.dart).
      context.pop();
    } catch (e) {
      if (!mounted) return;
      setState(() => _deleting = false);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Не удалось удалить полигон: $e')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(widget.polygon.label),
        actions: [
          IconButton(
            icon: _deleting
                ? const SizedBox(
                    width: 20,
                    height: 20,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Icon(Icons.delete_outline),
            tooltip: 'Удалить полигон',
            onPressed: (_loading || _deleting) ? null : _confirmDelete,
          ),
        ],
      ),
      body: _buildBody(),
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

    final restoredCount = _points.where((p) => p.isRestored).length;

    return LayoutBuilder(
      builder: (context, constraints) {
        final wide = constraints.maxWidth > 720;
        final content = [
          _PolygonHeader(polygon: widget.polygon, restoredCount: restoredCount, total: _points.length),
          const SizedBox(height: 16),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16),
            child: Text('primary_ndvi за последние 2 года',
                style: Theme.of(context).textTheme.titleMedium),
          ),
          const SizedBox(height: 8),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16),
            child: SizedBox(height: 260, child: NdviChart(points: _points)),
          ),
          const SizedBox(height: 8),
          const Padding(
            padding: EdgeInsets.symmetric(horizontal: 16),
            child: _ChartLegend(),
          ),
        ];

        final anomaliesList = _AnomaliesList(anomalies: _anomalies);

        if (!wide) {
          return SingleChildScrollView(
            padding: const EdgeInsets.only(bottom: 24),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                ...content,
                const SizedBox(height: 16),
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 16),
                  child: Text('Обнаруженные аномалии',
                      style: Theme.of(context).textTheme.titleMedium),
                ),
                anomaliesList,
              ],
            ),
          );
        }

        return Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Expanded(
              flex: 3,
              child: SingleChildScrollView(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: content,
                ),
              ),
            ),
            SizedBox(
              width: 340,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const SizedBox(height: 16),
                  Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 16),
                    child: Text('Обнаруженные аномалии',
                        style: Theme.of(context).textTheme.titleMedium),
                  ),
                  Expanded(child: anomaliesList),
                ],
              ),
            ),
          ],
        );
      },
    );
  }
}

class _PolygonHeader extends StatelessWidget {
  const _PolygonHeader({
    required this.polygon,
    required this.restoredCount,
    required this.total,
  });

  final NdviPolygon polygon;
  final int restoredCount;
  final int total;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(polygon.label,
                    style: Theme.of(context).textTheme.headlineSmall),
              ),
              if (polygon.isCustom)
                const Chip(label: Text('свой полигон'), visualDensity: VisualDensity.compact),
            ],
          ),
          const SizedBox(height: 4),
          Text('${polygon.id} · культура: ${polygon.cropType}',
              style: Theme.of(context).textTheme.bodyMedium),
          Text(
            'Восстановлено (gap-fill) $restoredCount из $total точек ряда',
            style: Theme.of(context).textTheme.bodySmall,
          ),
        ],
      ),
    );
  }
}

class _ChartLegend extends StatelessWidget {
  const _ChartLegend();

  @override
  Widget build(BuildContext context) {
    return Wrap(
      spacing: 16,
      runSpacing: 4,
      children: [
        _dot(const Color(0xFF2E7D32), 'Наблюдение (сплошная точка)'),
        _hollowDot(const Color(0xFF2E7D32), 'Восстановлено (кольцо)'),
        _dot(Colors.blueGrey, 'Климатическая норма'),
      ],
    );
  }

  Widget _dot(Color color, String label) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(
          width: 10,
          height: 10,
          decoration: BoxDecoration(color: color, shape: BoxShape.circle),
        ),
        const SizedBox(width: 6),
        Text(label, style: const TextStyle(fontSize: 11)),
      ],
    );
  }

  Widget _hollowDot(Color color, String label) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(
          width: 10,
          height: 10,
          decoration: BoxDecoration(
            color: Colors.white,
            shape: BoxShape.circle,
            border: Border.all(color: color, width: 2),
          ),
        ),
        const SizedBox(width: 6),
        Text(label, style: const TextStyle(fontSize: 11)),
      ],
    );
  }
}

class _AnomaliesList extends StatelessWidget {
  const _AnomaliesList({required this.anomalies});
  final List<Anomaly> anomalies;

  @override
  Widget build(BuildContext context) {
    if (anomalies.isEmpty) {
      return const Padding(
        padding: EdgeInsets.all(16),
        child: Text('Аномалий (Z < −1) за выбранный период не обнаружено.'),
      );
    }
    return ListView.builder(
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 8),
      itemCount: anomalies.length,
      itemBuilder: (context, i) {
        final a = anomalies[i];
        final range =
            '${DateFormat('MMM yyyy').format(a.startDate)} – ${DateFormat('MMM yyyy').format(a.endDate)}';
        return Card(
          margin: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
          child: ListTile(
            leading: Icon(
              a.severity == NdviStatus.critical ? Icons.error : Icons.warning_amber_rounded,
              color: statusColor(a.severity),
            ),
            title: Text(statusLabel(a.severity)),
            subtitle: Text(
              '$range\nмин. Z ${a.minZScore.toStringAsFixed(2)} · ΔNDVI ${a.deviation.toStringAsFixed(2)}\n${a.explanation}',
            ),
            isThreeLine: true,
          ),
        );
      },
    );
  }
}
