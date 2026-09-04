import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:go_router/go_router.dart';
import 'package:latlong2/latlong.dart' as ll;

import '../data/vegetation_data_service.dart';
import '../models/ndvi_point.dart';
import '../models/ndvi_polygon.dart';
import '../utils/ndvi_style.dart';
import '../widgets/time_slider.dart';

class MapScreen extends StatefulWidget {
  const MapScreen({super.key, required this.service});

  final VegetationDataService service;

  @override
  State<MapScreen> createState() => _MapScreenState();
}

class _MapScreenState extends State<MapScreen> {
  List<NdviPolygon> _polygons = [];
  final Map<String, List<NdviPoint>> _timeseries = {};
  List<DateTime> _dates = [];
  int _dateIndex = 0;
  bool _loading = true;
  String? _error;

  bool _drawing = false;
  final List<ll.LatLng> _draftPoints = [];
  bool _submittingDraft = false;

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
      final polygons = await widget.service.getPolygons();
      for (final p in polygons) {
        _timeseries[p.id] = await widget.service.getTimeseries(p.id);
      }
      final dates = _timeseries.values.expand((l) => l.map((p) => p.date)).toSet().toList()
        ..sort();
      setState(() {
        _polygons = polygons;
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

  NdviPoint? _pointAt(String polygonId, DateTime date) {
    final list = _timeseries[polygonId];
    if (list == null || list.isEmpty) return null;
    return list.reduce((a, b) =>
        (a.date.difference(date).abs() < b.date.difference(date).abs()) ? a : b);
  }

  void _toggleDrawing() {
    setState(() {
      _drawing = !_drawing;
      _draftPoints.clear();
    });
  }

  void _onMapTap(ll.LatLng point) {
    if (!_drawing) return;
    setState(() => _draftPoints.add(point));
  }

  Future<void> _finishDrawing() async {
    if (_draftPoints.length < 3) return;
    setState(() => _submittingDraft = true);
    try {
      final polygon = await widget.service.submitCustomPolygon(_draftPoints);
      if (!mounted) return;
      setState(() {
        _drawing = false;
        _draftPoints.clear();
        _submittingDraft = false;
      });
      context.push('/polygon/${polygon.id}', extra: polygon);
    } catch (e) {
      if (!mounted) return;
      setState(() => _submittingDraft = false);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Не удалось сохранить полигон: $e')),
      );
    }
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
      floatingActionButton: _loading || _error != null
          ? null
          : FloatingActionButton.extended(
              onPressed: _drawing
                  ? (_draftPoints.length >= 3 ? _finishDrawing : _toggleDrawing)
                  : _toggleDrawing,
              icon: Icon(_drawing
                  ? (_draftPoints.length >= 3 ? Icons.check : Icons.close)
                  : Icons.draw_outlined),
              label: Text(_drawing
                  ? (_draftPoints.length >= 3
                      ? 'Готово (${_draftPoints.length})'
                      : 'Отменить рисование')
                  : 'Нарисовать полигон'),
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
                options: MapOptions(
                  initialCenter: const ll.LatLng(10, 20),
                  initialZoom: 2.2,
                  minZoom: 2,
                  maxZoom: 16,
                  onTap: (tapPosition, point) => _onMapTap(point),
                ),
                children: [
                  TileLayer(
                    urlTemplate:
                        'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
                    userAgentPackageName: 'com.kosmohack.kosmohack_app',
                  ),
                  PolygonLayer(
                    polygons: [
                      for (final p in _polygons)
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
                      for (final p in _polygons)
                        Marker(
                          point: p.centroid,
                          width: 44,
                          height: 44,
                          child: _PolygonPin(
                            polygon: p,
                            status: _pointAt(p.id, selectedDate)?.status,
                            onTap: () =>
                                context.push('/polygon/${p.id}', extra: p),
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
              if (_submittingDraft)
                const Positioned.fill(
                  child: ColoredBox(
                    color: Colors.black26,
                    child: Center(child: CircularProgressIndicator()),
                  ),
                ),
              const Positioned(left: 12, top: 12, child: _Legend()),
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
            Text('Z-score', style: Theme.of(context).textTheme.labelLarge),
            const SizedBox(height: 4),
            _legendRow(NdviStatus.normal, 'Z ≥ −1'),
            _legendRow(NdviStatus.suppression, '−2 ≤ Z < −1'),
            _legendRow(NdviStatus.critical, 'Z < −2'),
          ],
        ),
      ),
    );
  }

  Widget _legendRow(NdviStatus status, String range) {
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
          Text('${statusLabel(status)} ($range)', style: const TextStyle(fontSize: 11)),
        ],
      ),
    );
  }
}
