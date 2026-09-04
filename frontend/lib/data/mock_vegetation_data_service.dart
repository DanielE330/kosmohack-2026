import 'dart:math';

import 'package:latlong2/latlong.dart';

import '../models/anomaly.dart';
import '../models/demo_area.dart';
import '../models/ndvi_point.dart';
import '../models/ndvi_polygon.dart';
import 'vegetation_data_service.dart';

/// Фейковый бэкенд на время, пока не готов реальный пайплайн обработки
/// данных (приём GEE/Copernicus + восстановление пропусков + сервис
/// аномалий по Z-score). Содержит три демо-территории, у каждой по паре
/// полигонов, так что сюжет с аномалией всегда демонстрируем офлайн — и
/// моделирует ту же форму данных, что будет у реального API: временной
/// ряд по полигону с наблюдениями `primary_ndvi`, синтетическими/
/// естественными пропусками, восстановленными значениями и полосой
/// климатической нормы.
class MockVegetationDataService implements VegetationDataService {
  MockVegetationDataService() {
    _generateAll();
  }

  static const _areas = [
    DemoArea(
      id: 'mekong-delta',
      name: 'Дельта Меконга',
      country: 'Вьетнам',
      lat: 10.03,
      lon: 105.78,
      description: 'Рисовые чеки, сильная засуха 2019–2020.',
    ),
    DemoArea(
      id: 'paradise-ca',
      name: 'Парадайз, Калифорния',
      country: 'США',
      lat: 39.76,
      lon: -121.62,
      description: 'Сады/пастбища рядом с зоной пожара Camp Fire, 2018.',
    ),
    DemoArea(
      id: 'rondonia-br',
      name: 'Рондония',
      country: 'Бразилия',
      lat: -10.9,
      lon: -62.8,
      description: 'Бывший лес, распаханный под пастбище, 2021–2022.',
    ),
  ];

  static const _cropTypeByArea = {
    'mekong-delta': 'rice',
    'paradise-ca': 'orchard',
    'rondonia-br': 'pasture',
  };

  final List<NdviPolygon> _polygons = [];
  final Map<String, List<NdviPoint>> _timeseries = {};
  final Map<String, List<Anomaly>> _anomalies = {};
  int _customCounter = 0;

  void _generateAll() {
    for (final area in _areas) {
      for (int i = 0; i < 2; i++) {
        final polygon = _makePolygon(area, i);
        _polygons.add(polygon);
        final points = _generateSeries(area.id, seedOffset: i);
        _timeseries[polygon.id] = points;
        _anomalies[polygon.id] = _buildAnomalies(polygon.id, area.id, points);
      }
    }
  }

  NdviPolygon _makePolygon(DemoArea area, int index) {
    // Небольшие прямоугольники со смещением от центра территории — заглушка
    // вместо реальных контуров полей OSM/ESA WorldCereal.
    final dLat = 0.01 + index * 0.018;
    final dLon = 0.01 + index * 0.018;
    final corners = [
      LatLng(area.lat - dLat, area.lon - dLon),
      LatLng(area.lat - dLat, area.lon + dLon),
      LatLng(area.lat + dLat, area.lon + dLon),
      LatLng(area.lat + dLat, area.lon - dLon),
    ];
    return NdviPolygon(
      id: 'AOI-${area.id}-${index + 1}',
      label: '${area.name}, участок ${index + 1}',
      cropType: _cropTypeByArea[area.id] ?? 'unknown',
      areaId: area.id,
      points: corners,
    );
  }

  /// Гладкая сезонная база (без аномалии и без шума) — из неё же считается
  /// среднее/std климатической нормы.
  double _seasonal(DateTime date) {
    final dayOfYear = date.difference(DateTime(date.year, 1, 1)).inDays;
    return 0.55 + 0.2 * sin((dayOfYear / 365.0) * 2 * pi);
  }

  /// Величина (положительное число, вычитается) сценарной аномалии на
  /// момент [t] дней от начала ряда, для каждой демо-территории.
  double _anomalyDepth(String areaId, int t) {
    switch (areaId) {
      case 'mekong-delta':
        // Засуха: нарастает, выходит на плато, медленно восстанавливается.
        const start = 420, rampUp = 60, plateau = 60, rampDown = 90;
        if (t < start || t > start + rampUp + plateau + rampDown) return 0;
        final into = t - start;
        if (into < rampUp) return 0.32 * (into / rampUp);
        if (into < rampUp + plateau) return 0.32;
        final decayInto = into - rampUp - plateau;
        return 0.32 * (1 - decayInto / rampDown);
      case 'paradise-ca':
        // Пожар: резкое падение, медленное восстановление за ~7 месяцев.
        const start = 300, recovery = 210;
        if (t < start) return 0;
        if (t > start + recovery) return 0;
        return 0.42 * (1 - (t - start) / recovery);
      case 'rondonia-br':
        // Вырубка под пастбище: постоянное ступенчатое снижение, усиливается.
        const start = 240;
        if (t < start) return 0;
        final monthsIn = (t - start) / 30.0;
        return (0.15 + min(monthsIn * 0.015, 0.25));
      default:
        return 0;
    }
  }

  List<NdviPoint> _generateSeries(String areaId, {required int seedOffset}) {
    final rand = Random(42 + seedOffset);
    final start = DateTime.now().subtract(const Duration(days: 730));
    final points = <NdviPoint>[];

    final trueValues = <int, double>{};
    final observed = <int, bool>{};
    final isSynthetic = <int, bool>{};

    const stepDays = 8;
    final steps = 730 ~/ stepDays;

    for (int i = 0; i <= steps; i++) {
      final t = i * stepDays;
      final date = start.add(Duration(days: t));
      final seasonal = _seasonal(date);
      final depth = _anomalyDepth(areaId, t);
      final noise = (rand.nextDouble() - 0.5) * 0.03;
      trueValues[i] = (seasonal - depth + noise).clamp(0.02, 0.95);

      // ~22% шанс отсутствия пригодного спутникового наблюдения (облако/тень).
      final isGap = rand.nextDouble() < 0.22;
      observed[i] = !isGap;
      // Из пропусков ~40% — скрытые контрольные точки организаторов.
      isSynthetic[i] = isGap && rand.nextDouble() < 0.4;
    }

    for (int i = 0; i <= steps; i++) {
      final t = i * stepDays;
      final date = start.add(Duration(days: t));
      final seasonalMean = _seasonal(date);

      double? observedNdvi;
      double restoredNdvi;
      if (observed[i]!) {
        observedNdvi = trueValues[i];
        restoredNdvi = trueValues[i]!;
      } else {
        observedNdvi = null;
        restoredNdvi = _interpolate(trueValues, i, steps);
      }

      points.add(NdviPoint(
        date: date,
        observedNdvi: observedNdvi,
        restoredNdvi: restoredNdvi,
        isSyntheticGap: isSynthetic[i]!,
        climatologyMean: seasonalMean.clamp(0.05, 0.9),
        climatologyStd: 0.06,
        cropType: _cropTypeByArea[areaId] ?? 'unknown',
      ));
    }
    return points;
  }

  /// Базовое восстановление пропуска: среднее «истинных» значений
  /// соседних шагов (на краях ряда берётся та сторона, что есть) — тот же
  /// простой подход, что описан в ТЗ как стартовый baseline.
  double _interpolate(Map<int, double> trueValues, int index, int maxIndex) {
    final before = index > 0 ? trueValues[index - 1] : null;
    final after = index < maxIndex ? trueValues[index + 1] : null;
    if (before != null && after != null) return (before + after) / 2;
    return before ?? after ?? trueValues[index]!;
  }

  List<Anomaly> _buildAnomalies(
    String polygonId,
    String areaId,
    List<NdviPoint> points,
  ) {
    final anomalies = <Anomaly>[];
    bool inRun = false;
    int runStart = 0;

    for (int i = 0; i < points.length; i++) {
      final anomalous = points[i].status != NdviStatus.normal;
      if (anomalous && !inRun) {
        inRun = true;
        runStart = i;
      }
      if (!anomalous && inRun) {
        anomalies.add(_anomalyFor(polygonId, areaId, points, runStart, i - 1));
        inRun = false;
      }
    }
    if (inRun) {
      anomalies.add(_anomalyFor(polygonId, areaId, points, runStart, points.length - 1));
    }
    return anomalies;
  }

  Anomaly _anomalyFor(
    String polygonId,
    String areaId,
    List<NdviPoint> points,
    int startIdx,
    int endIdx,
  ) {
    final run = points.sublist(startIdx, endIdx + 1);
    final worst = run.reduce((a, b) => a.zScore < b.zScore ? a : b);

    late String explanation;
    switch (areaId) {
      case 'mekong-delta':
        explanation = 'Продолжительное отклонение NDVI ниже климатической нормы '
            'совпадает с сезоном муссонной засухи — Z-score восстанавливается '
            'медленно, что типично для нехватки влаги, а не единовременного '
            'события.';
        break;
      case 'paradise-ca':
        explanation = 'Резкое однократное падение Z-score с последующим '
            'постепенным ростом — характерная сигнатура пожара и '
            'последующей регенерации растительности.';
        break;
      case 'rondonia-br':
        explanation = 'Ступенчатое и не восстанавливающееся снижение Z-score, '
            'усиливающееся со временем — признак систематической распашки '
            'под пастбище, а не сезонного стресса.';
        break;
      default:
        explanation = 'Устойчивое отклонение NDVI от климатической нормы.';
    }

    return Anomaly(
      id: '$polygonId-${points[startIdx].date.toIso8601String()}',
      polygonId: polygonId,
      startDate: points[startIdx].date,
      endDate: points[endIdx].date,
      severity: worst.status,
      minZScore: worst.zScore,
      deviation: worst.value - worst.climatologyMean,
      explanation: explanation,
    );
  }

  @override
  List<DemoArea> getDemoAreas() => _areas;

  @override
  Future<List<NdviPolygon>> getPolygons() async => _polygons;

  @override
  Future<NdviPolygon> submitCustomPolygon(List<LatLng> points) async {
    _customCounter++;
    final id = 'CUSTOM-$_customCounter';
    final centroidLat = points.map((p) => p.latitude).reduce((a, b) => a + b) / points.length;
    final centroidLon = points.map((p) => p.longitude).reduce((a, b) => a + b) / points.length;

    // Ближайшая демо-территория определяет, какой сценарий аномалии
    // унаследует нарисованный полигон — так демо остаётся связным, где бы
    // пользователь ни рисовал.
    final nearest = _areas.reduce((a, b) {
      final da = _dist(a.lat, a.lon, centroidLat, centroidLon);
      final db = _dist(b.lat, b.lon, centroidLat, centroidLon);
      return da < db ? a : b;
    });

    final polygon = NdviPolygon(
      id: id,
      label: 'Мой полигон $_customCounter',
      cropType: _cropTypeByArea[nearest.id] ?? 'unknown',
      areaId: nearest.id,
      points: points,
      isCustom: true,
    );
    _polygons.add(polygon);
    final series = _generateSeries(nearest.id, seedOffset: 10 + _customCounter);
    _timeseries[id] = series;
    _anomalies[id] = _buildAnomalies(id, nearest.id, series);
    return polygon;
  }

  double _dist(double lat1, double lon1, double lat2, double lon2) {
    final dLat = lat1 - lat2;
    final dLon = lon1 - lon2;
    return dLat * dLat + dLon * dLon;
  }

  @override
  Future<List<NdviPoint>> getTimeseries(String polygonId) async =>
      _timeseries[polygonId] ?? [];

  @override
  Future<List<Anomaly>> getAnomalies({String? polygonId}) async {
    if (polygonId != null) return _anomalies[polygonId] ?? [];
    return _anomalies.values.expand((a) => a).toList();
  }
}
