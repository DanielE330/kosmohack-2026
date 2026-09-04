import 'package:flutter_test/flutter_test.dart';
import 'package:latlong2/latlong.dart';

import 'package:kosmohack_app/data/mock_vegetation_data_service.dart';
import 'package:kosmohack_app/models/ndvi_point.dart';

void main() {
  late MockVegetationDataService service;

  setUp(() {
    service = MockVegetationDataService();
  });

  test('exposes field polygons for all three demo areas', () async {
    final polygons = await service.getPolygons();
    expect(polygons.length, 6);
    expect(polygons.map((p) => p.areaId).toSet(), {
      'mekong-delta',
      'paradise-ca',
      'rondonia-br',
    });
  });

  test('each polygon has a ~2-year time series with some restored points',
      () async {
    final polygons = await service.getPolygons();
    for (final polygon in polygons) {
      final points = await service.getTimeseries(polygon.id);
      expect(points.length, greaterThan(80));
      expect(points.every((p) => p.value >= 0 && p.value <= 1), isTrue);
      expect(points.any((p) => p.isRestored), isTrue,
          reason: 'gap-filling must be exercised for the demo');
    }
  });

  test('each polygon has at least one detected anomaly', () async {
    final polygons = await service.getPolygons();
    for (final polygon in polygons) {
      final anomalies = await service.getAnomalies(polygonId: polygon.id);
      expect(anomalies, isNotEmpty,
          reason: '${polygon.id} must reliably show an anomaly for the demo');
    }
  });

  test('anomaly severities follow the spec\'s Z-score thresholds', () async {
    final polygons = await service.getPolygons();
    for (final polygon in polygons) {
      final points = await service.getTimeseries(polygon.id);
      for (final p in points) {
        expect(p.status, ndviStatusForZ(p.zScore));
      }
    }
  });

  test('a hand-drawn custom polygon gets its own time series', () async {
    // Примерный прямоугольник рядом с демо-территорией дельты Меконга.
    final polygon = await service.submitCustomPolygon(const [
      LatLng(10.0, 105.7),
      LatLng(10.0, 105.8),
      LatLng(10.1, 105.8),
      LatLng(10.1, 105.7),
    ]);

    expect(polygon.isCustom, isTrue);
    final points = await service.getTimeseries(polygon.id);
    expect(points, isNotEmpty);
  });
}
