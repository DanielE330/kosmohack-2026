import 'package:flutter_test/flutter_test.dart';
import 'package:latlong2/latlong.dart';

import 'package:kosmohack_app/data/mock_vegetation_data_service.dart';
import 'package:kosmohack_app/models/ndvi_point.dart';

void main() {
  late MockVegetationDataService service;

  setUp(() {
    service = MockVegetationDataService();
  });

  test('starts with no pre-seeded polygons — only what the user creates',
      () async {
    final polygons = await service.getPolygons();
    expect(polygons, isEmpty);
  });

  test('still exposes the three reference areas for crop-type lookup', () {
    final areas = service.getDemoAreas();
    expect(areas.map((a) => a.id).toSet(), {
      'rostov-wheat',
      'krasnodar-sunflower',
      'stavropol-pasture',
    });
  });

  test('each hand-drawn polygon has a ~2-year time series with some restored points',
      () async {
    final polygon = await service.submitCustomPolygon(const [
      LatLng(47.5, 40.0),
      LatLng(47.5, 40.1),
      LatLng(47.6, 40.1),
      LatLng(47.6, 40.0),
    ]);
    final points = await service.getTimeseries(polygon.id);
    expect(points.length, greaterThan(80));
    expect(points.every((p) => p.value >= 0 && p.value <= 1), isTrue);
    expect(points.any((p) => p.isRestored), isTrue,
        reason: 'gap-filling must be exercised for the demo');
  });

  test('a hand-drawn polygon reliably shows a detected anomaly', () async {
    final polygon = await service.submitCustomPolygon(const [
      LatLng(47.5, 40.0),
      LatLng(47.5, 40.1),
      LatLng(47.6, 40.1),
      LatLng(47.6, 40.0),
    ]);
    final anomalies = await service.getAnomalies(polygonId: polygon.id);
    expect(anomalies, isNotEmpty,
        reason: '${polygon.id} must reliably show an anomaly for the demo');
  });

  test('anomaly severities follow the spec\'s Z-score thresholds', () async {
    final polygon = await service.submitCustomPolygon(const [
      LatLng(47.5, 40.0),
      LatLng(47.5, 40.1),
      LatLng(47.6, 40.1),
      LatLng(47.6, 40.0),
    ]);
    final points = await service.getTimeseries(polygon.id);
    for (final p in points) {
      expect(p.status, ndviStatusForZ(p.zScore));
    }
  });

  test('a hand-drawn custom polygon gets its own time series', () async {
    // Примерный прямоугольник рядом с демо-территорией Ростовской области.
    final polygon = await service.submitCustomPolygon(const [
      LatLng(47.5, 40.0),
      LatLng(47.5, 40.1),
      LatLng(47.6, 40.1),
      LatLng(47.6, 40.0),
    ]);

    expect(polygon.isCustom, isTrue);
    final points = await service.getTimeseries(polygon.id);
    expect(points, isNotEmpty);
  });

  test('deleting a polygon removes it and its data', () async {
    final polygon = await service.submitCustomPolygon(const [
      LatLng(47.5, 40.0),
      LatLng(47.5, 40.1),
      LatLng(47.6, 40.1),
      LatLng(47.6, 40.0),
    ]);

    await service.deletePolygon(polygon.id);

    final polygons = await service.getPolygons();
    expect(polygons.any((p) => p.id == polygon.id), isFalse);
    expect(await service.getTimeseries(polygon.id), isEmpty);
    expect(await service.getAnomalies(polygonId: polygon.id), isEmpty);
  });

  test('findPolygonsInRegion returns an already-known (user-drawn) polygon inside the bbox',
      () async {
    final drawn = await service.submitCustomPolygon(const [
      LatLng(47.5, 40.0),
      LatLng(47.5, 40.02),
      LatLng(47.52, 40.02),
      LatLng(47.52, 40.0),
    ]);
    final found = await service.findPolygonsInRegion(
      minLat: 47.4,
      minLon: 39.9,
      maxLat: 47.6,
      maxLon: 40.1,
    );
    expect(found.any((p) => p.id == drawn.id), isTrue);
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
