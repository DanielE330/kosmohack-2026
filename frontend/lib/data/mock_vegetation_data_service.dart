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

  // Демо-территории соответствуют реальному датасету соревнования
  // (`data/train_dataset.csv`) — южная степная зона России, реальные
  // культуры (озимая пшеница/подсолнечник/пастбища), координаты в том же
  // районе, что и настоящие AOI бэкенда (~47°с.ш., ~39°в.д., см.
  // `tasks/backend.md`). Раньше здесь были международные кейсы (дельта
  // Меконга/Калифорния/Рондония) — заменены, чтобы демо не вводило в
  // заблуждение по факту реальных данных.
  static const _areas = [
    DemoArea(
      id: 'rostov-wheat',
      name: 'Ростовская область',
      country: 'Россия',
      lat: 47.5,
      lon: 40.0,
      description: 'Озимая пшеница, почвенная засуха в фазу колошения.',
    ),
    DemoArea(
      id: 'krasnodar-sunflower',
      name: 'Краснодарский край',
      country: 'Россия',
      lat: 45.3,
      lon: 39.0,
      description: 'Подсолнечник, повреждение посевов градом.',
    ),
    DemoArea(
      id: 'stavropol-pasture',
      name: 'Ставропольский край',
      country: 'Россия',
      lat: 44.8,
      lon: 42.5,
      description: 'Пастбища/зерновые, деградация почвы без севооборота.',
    ),
  ];

  static const _cropTypeByArea = {
    'rostov-wheat': 'озимая пшеница',
    'krasnodar-sunflower': 'подсолнечник',
    'stavropol-pasture': 'пастбища/зерновые',
  };

  final List<NdviPolygon> _polygons = [];
  final Map<String, List<NdviPoint>> _timeseries = {};
  final Map<String, List<Anomaly>> _anomalies = {};
  int _customCounter = 0;
  int _foundCounter = 0;

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
      case 'rostov-wheat':
        // Почвенная засуха: нарастает к колошению, плато, медленно отходит.
        const start = 420, rampUp = 60, plateau = 60, rampDown = 90;
        if (t < start || t > start + rampUp + plateau + rampDown) return 0;
        final into = t - start;
        if (into < rampUp) return 0.32 * (into / rampUp);
        if (into < rampUp + plateau) return 0.32;
        final decayInto = into - rampUp - plateau;
        return 0.32 * (1 - decayInto / rampDown);
      case 'krasnodar-sunflower':
        // Град: резкое однократное повреждение, восстановление за ~7 мес.
        const start = 300, recovery = 210;
        if (t < start) return 0;
        if (t > start + recovery) return 0;
        return 0.42 * (1 - (t - start) / recovery);
      case 'stavropol-pasture':
        // Деградация почвы без севооборота: постоянное снижение, усиливается.
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
      // Мок всегда генерирует климатологию, поэтому здесь она точно известна.
      deviation: worst.value - worst.climatologyMean!,
      explanation: explanation,
    );
  }

  @override
  bool get requiresAuth => false;

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
    final nearest = _nearestArea(centroidLat, centroidLon);

    final polygon = NdviPolygon(
      id: id,
      label: 'Мой полигон $_customCounter',
      cropType: _cropTypeByArea[nearest.id] ?? 'unknown',
      areaId: nearest.id,
      // Копируем список: caller (MapScreen) переиспользует и очищает свой
      // `_draftPoints` сразу после отправки, и если бы мы хранили ту же
      // ссылку, у только что созданного полигона мгновенно опустел бы
      // `points` — а `NdviPolygon.centroid` на пустом списке падает с
      // `Bad state: No element` при следующей перерисовке карты.
      points: List<LatLng>.from(points),
      isCustom: true,
    );
    _polygons.add(polygon);
    final series = _generateSeries(nearest.id, seedOffset: 10 + _customCounter);
    _timeseries[id] = series;
    _anomalies[id] = _buildAnomalies(id, nearest.id, series);
    return polygon;
  }

  @override
  Future<NdviPolygon> updatePolygon(
    String polygonId, {
    String? label,
    String? cropType,
    List<LatLng>? points,
  }) async {
    final index = _polygons.indexWhere((p) => p.id == polygonId);
    if (index == -1) {
      throw Exception('Полигон $polygonId не найден');
    }
    final current = _polygons[index];
    final updated = NdviPolygon(
      id: current.id,
      label: label ?? current.label,
      cropType: cropType ?? current.cropType,
      areaId: current.areaId,
      points: points ?? current.points,
      isCustom: current.isCustom,
    );
    _polygons[index] = updated;
    return updated;
  }

  @override
  Future<void> deletePolygon(String polygonId) async {
    _polygons.removeWhere((p) => p.id == polygonId);
    _timeseries.remove(polygonId);
    _anomalies.remove(polygonId);
  }

  @override
  Future<List<NdviPolygon>> findPolygonsInRegion({
    required double minLat,
    required double minLon,
    required double maxLat,
    required double maxLon,
  }) async {
    // Сначала смотрим, что из уже известных полигонов попадает в область —
    // так повторный поиск по тому же месту не плодит дублей.
    final existing = _polygons.where((p) {
      final c = p.centroid;
      return c.latitude >= minLat &&
          c.latitude <= maxLat &&
          c.longitude >= minLon &&
          c.longitude <= maxLon;
    }).toList();
    if (existing.isNotEmpty) return existing;

    // Ничего нет — эмулируем автопоиск открытых сельхозконтуров
    // (OSM/ESA WorldCereal) для новой территории: генерируем пару
    // правдоподобных полигонов внутри области.
    final centerLat = (minLat + maxLat) / 2;
    final centerLon = (minLon + maxLon) / 2;
    final nearest = _nearestArea(centerLat, centerLon);
    final dLat = (maxLat - minLat).abs() * 0.12;
    final dLon = (maxLon - minLon).abs() * 0.12;
    if (dLat == 0 || dLon == 0) return [];

    final found = <NdviPolygon>[];
    for (int i = 0; i < 2; i++) {
      _foundCounter++;
      final id = 'FOUND-$_foundCounter';
      final sign = i == 0 ? -1 : 1;
      final cLat = centerLat + sign * dLat;
      final cLon = centerLon + sign * dLon;
      final polygon = NdviPolygon(
        id: id,
        label: 'Найденный контур $_foundCounter',
        cropType: _cropTypeByArea[nearest.id] ?? 'unknown',
        areaId: nearest.id,
        points: [
          LatLng(cLat - dLat, cLon - dLon),
          LatLng(cLat - dLat, cLon + dLon),
          LatLng(cLat + dLat, cLon + dLon),
          LatLng(cLat + dLat, cLon - dLon),
        ],
      );
      _polygons.add(polygon);
      final series = _generateSeries(nearest.id, seedOffset: 20 + _foundCounter);
      _timeseries[id] = series;
      _anomalies[id] = _buildAnomalies(id, nearest.id, series);
      found.add(polygon);
    }
    return found;
  }

  DemoArea _nearestArea(double lat, double lon) {
    return _areas.reduce((a, b) {
      final da = _dist(a.lat, a.lon, lat, lon);
      final db = _dist(b.lat, b.lon, lat, lon);
      return da < db ? a : b;
    });
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
