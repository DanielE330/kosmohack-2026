import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:go_router/go_router.dart';
import 'package:latlong2/latlong.dart' as ll;

import '../data/vegetation_data_service.dart';
import '../models/anomaly.dart';
import '../models/ndvi_point.dart';
import '../models/region.dart';
import '../utils/ndvi_style.dart';
import '../widgets/time_slider.dart';

class MapScreen extends StatefulWidget {
  const MapScreen({super.key, required this.service});

  final VegetationDataService service;

  @override
  State<MapScreen> createState() => _MapScreenState();
}

class _MapScreenState extends State<MapScreen> {
  List<Region> _regions = [];
  final Map<String, List<NdviPoint>> _timeseries = {};
  final Map<String, List<Anomaly>> _anomalies = {};
  List<DateTime> _dates = [];
  int _dateIndex = 0;
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
      final regions = await widget.service.getRegions();
      for (final r in regions) {
        _timeseries[r.id] = await widget.service.getTimeseries(r.id);
        _anomalies[r.id] = await widget.service.getAnomalies(regionId: r.id);
      }
      final dates = _timeseries.values.expand((l) => l.map((p) => p.date)).toSet().toList()
        ..sort();
      setState(() {
        _regions = regions;
        _dates = dates;
        _dateIndex = dates.isEmpty ? 0 : dates.length - 1;
        _loading = false;
      });
    } catch (e) {
      setState(() {
        _error = 'Не удалось загрузить данные: $e';
        _loading = false;
      });
    }
  }

  NdviPoint? _pointAt(String regionId, DateTime date) {
    final list = _timeseries[regionId];
    if (list == null || list.isEmpty) return null;
    return list.reduce((a, b) =>
        (a.date.difference(date).abs() < b.date.difference(date).abs()) ? a : b);
  }

  bool _isAnomalousAt(String regionId, DateTime date) {
    final anomalies = _anomalies[regionId] ?? [];
    return anomalies.any((a) =>
        !date.isBefore(a.startDate) && !date.isAfter(a.endDate ?? a.startDate));
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('NDVI-мониторинг'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            tooltip: 'Обновить',
            onPressed: _loading ? null : _load,
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

    final selectedDate = _dates.isEmpty ? DateTime.now() : _dates[_dateIndex];

    return Column(
      children: [
        Expanded(
          child: Stack(
            children: [
              FlutterMap(
                options: const MapOptions(
                  initialCenter: ll.LatLng(10, 20),
                  initialZoom: 2.2,
                  minZoom: 2,
                  maxZoom: 12,
                ),
                children: [
                  TileLayer(
                    urlTemplate:
                        'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
                    userAgentPackageName: 'com.kosmohack.kosmohack_app',
                  ),
                  CircleLayer(
                    circles: [
                      for (final r in _regions)
                        if (_pointAt(r.id, selectedDate) != null)
                          CircleMarker(
                            point: ll.LatLng(r.lat, r.lon),
                            radius: 26,
                            useRadiusInMeter: false,
                            color: ndviColor(_pointAt(r.id, selectedDate)!.ndvi)
                                .withValues(alpha: 0.55),
                            borderColor:
                                ndviColor(_pointAt(r.id, selectedDate)!.ndvi),
                            borderStrokeWidth: 2,
                          ),
                    ],
                  ),
                  MarkerLayer(
                    markers: [
                      for (final r in _regions)
                        Marker(
                          point: ll.LatLng(r.lat, r.lon),
                          width: 44,
                          height: 44,
                          child: _RegionPin(
                            region: r,
                            anomalous: _isAnomalousAt(r.id, selectedDate),
                            onTap: () =>
                                context.push('/region/${r.id}', extra: r),
                          ),
                        ),
                    ],
                  ),
                ],
              ),
              Positioned(
                left: 12,
                top: 12,
                child: _Legend(),
              ),
            ],
          ),
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

class _RegionPin extends StatelessWidget {
  const _RegionPin({
    required this.region,
    required this.anomalous,
    required this.onTap,
  });

  final Region region;
  final bool anomalous;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Tooltip(
      message: region.name,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(22),
        child: Icon(
          anomalous ? Icons.warning_rounded : Icons.location_on,
          color: anomalous ? const Color(0xFFB3261E) : const Color(0xFF2E7D32),
          size: 34,
          shadows: const [Shadow(blurRadius: 4, color: Colors.black45)],
        ),
      ),
    );
  }
}

class _Legend extends StatelessWidget {
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
            Text('NDVI', style: Theme.of(context).textTheme.labelLarge),
            const SizedBox(height: 4),
            _legendRow(0.85, 'Здоровая растительность'),
            _legendRow(0.45, 'Умеренный стресс'),
            _legendRow(0.15, 'Сильное отклонение'),
            const SizedBox(height: 6),
            Row(
              children: [
                const Icon(Icons.warning_rounded,
                    color: Color(0xFFB3261E), size: 16),
                const SizedBox(width: 6),
                Text('Аномалия', style: Theme.of(context).textTheme.bodySmall),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _legendRow(double ndvi, String label) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 2),
      child: Row(
        children: [
          Container(
            width: 12,
            height: 12,
            decoration:
                BoxDecoration(color: ndviColor(ndvi), shape: BoxShape.circle),
          ),
          const SizedBox(width: 6),
          Text(label, style: const TextStyle(fontSize: 11)),
        ],
      ),
    );
  }
}
