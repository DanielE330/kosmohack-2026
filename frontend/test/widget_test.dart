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

  test('deleting a polygon removes it and its data', () async {
    final polygon = await service.submitCustomPolygon(const [
      LatLng(10.0, 105.7),
      LatLng(10.0, 105.8),
      LatLng(10.1, 105.8),
      LatLng(10.1, 105.7),
    ]);

    await service.deletePolygon(polygon.id);

    final polygons = await service.getPolygons();
    expect(polygons.any((p) => p.id == polygon.id), isFalse);
    expect(await service.getTimeseries(polygon.id), isEmpty);
    expect(await service.getAnomalies(polygonId: polygon.id), isEmpty);
  });

  test('findPolygonsInRegion returns already-known polygons inside the bbox',
      () async {
    // Дельта Меконга — оба демо-полигона в пределах ~0.05°.
    final found = await service.findPolygonsInRegion(
      minLat: 9.9,
      minLon: 105.6,
      maxLat: 10.2,
      maxLon: 105.9,
    );
    expect(found, isNotEmpty);
    expect(found.every((p) => p.areaId == 'mekong-delta'), isTrue);
  });

  test('findPolygonsInRegion auto-discovers contours for an empty area',
      () async {
    // Область без демо-полигонов и без запусков "нарисовать" — сервис
    // должен сам предложить найденные контуры.
    final found = await service.findPolygonsInRegion(
      minLat: 45.0,
      minLon: 40.0,
      maxLat: 45.2,
      maxLon: 40.2,
    );
    expect(found.length, 2);
    expect(found.every((p) => !p.isCustom), isTrue);

    for (final polygon in found) {
      expect(await service.getTimeseries(polygon.id), isNotEmpty);
    }
  });

  test(
      'NdviPoint.fromJson tolerates null climatology '
      '(real backend masks it for gap rows)', () {
    final point = NdviPoint.fromJson({
      'date': '2010-04-01',
      'primary_ndvi': null,
      'primary_ndvi_pred': 0.33,
      'is_synthetic_gap': false,
      'climatology_mean': null,
      'climatology_std': null,
      'crop_type': 'озимая пшеница',
    });

    expect(point.hasClimatology, isFalse);
    expect(point.zScore, 0);
    expect(point.status, NdviStatus.normal);
    expect(point.value, 0.33);
  });
}
