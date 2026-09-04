import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

import '../data/vegetation_data_service.dart';
import '../models/anomaly.dart';
import '../models/ndvi_point.dart';
import '../models/region.dart';
import '../utils/ndvi_style.dart';
import '../widgets/ndvi_chart.dart';

class RegionDetailScreen extends StatefulWidget {
  const RegionDetailScreen({
    super.key,
    required this.service,
    required this.region,
  });

  final VegetationDataService service;
  final Region region;

  @override
  State<RegionDetailScreen> createState() => _RegionDetailScreenState();
}

class _RegionDetailScreenState extends State<RegionDetailScreen> {
  List<NdviPoint> _points = [];
  List<Anomaly> _anomalies = [];
  bool _loading = true;
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
      final points = await widget.service.getTimeseries(widget.region.id);
      final anomalies =
          await widget.service.getAnomalies(regionId: widget.region.id);
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

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(widget.region.name),
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

    return LayoutBuilder(
      builder: (context, constraints) {
        final wide = constraints.maxWidth > 720;
        final content = [
          _RegionHeader(region: widget.region),
          const SizedBox(height: 16),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16),
            child: Text('NDVI за последние 2 года',
                style: Theme.of(context).textTheme.titleMedium),
          ),
          const SizedBox(height: 8),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16),
            child: SizedBox(height: 260, child: NdviChart(points: _points)),
          ),
          const SizedBox(height: 8),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16),
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

class _RegionHeader extends StatelessWidget {
  const _RegionHeader({required this.region});
  final Region region;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('${region.name}, ${region.country}',
              style: Theme.of(context).textTheme.headlineSmall),
          const SizedBox(height: 4),
          Text(region.description, style: Theme.of(context).textTheme.bodyMedium),
        ],
      ),
    );
  }
}

class _ChartLegend extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Wrap(
      spacing: 16,
      runSpacing: 4,
      children: [
        _dot(const Color(0xFF2E7D32), 'Фактический NDVI'),
        _dot(Colors.blueGrey, 'Климатическая норма'),
        _dot(const Color(0xFFB3261E), 'Аномальная точка'),
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
}

class _AnomaliesList extends StatelessWidget {
  const _AnomaliesList({required this.anomalies});
  final List<Anomaly> anomalies;

  @override
  Widget build(BuildContext context) {
    if (anomalies.isEmpty) {
      return const Padding(
        padding: EdgeInsets.all(16),
        child: Text('Аномалий за выбранный период не обнаружено.'),
      );
    }
    return ListView.builder(
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 8),
      itemCount: anomalies.length,
      itemBuilder: (context, i) {
        final a = anomalies[i];
        final range = a.endDate != null
            ? '${DateFormat('MMM yyyy').format(a.startDate)} – ${DateFormat('MMM yyyy').format(a.endDate!)}'
            : DateFormat('MMM yyyy').format(a.startDate);
        return Card(
          margin: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
          child: ListTile(
            leading: Icon(anomalyIcon(a.type), color: severityColor(a.severity)),
            title: Text('${anomalyTypeLabel(a.type)} · ${severityLabel(a.severity)}'),
            subtitle: Text(
              '$range\nΔNDVI ${a.deviation.toStringAsFixed(2)}\n${a.explanation}',
            ),
            isThreeLine: true,
          ),
        );
      },
    );
  }
}
