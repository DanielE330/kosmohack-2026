import 'dart:math';

import '../models/anomaly.dart';
import '../models/ndvi_point.dart';
import '../models/region.dart';
import 'vegetation_data_service.dart';

/// Fake backend used until the real FastAPI service is ready. Ships with
/// three demo regions that mirror real, well-known events, so the anomaly
/// story is always demonstrable even offline.
class MockVegetationDataService implements VegetationDataService {
  MockVegetationDataService() {
    _generateAll();
  }

  static final List<Region> _regions = [
    const Region(
      id: 'mekong-delta',
      name: 'Дельта Меконга',
      country: 'Вьетнам',
      lat: 10.03,
      lon: 105.78,
      description: 'Сильная засуха 2019–2020: падение NDVI в рисовых чеках.',
    ),
    const Region(
      id: 'paradise-ca',
      name: 'Парадайз, Калифорния',
      country: 'США',
      lat: 39.76,
      lon: -121.62,
      description: 'Camp Fire, ноябрь 2018: резкая потеря растительности.',
    ),
    const Region(
      id: 'rondonia-br',
      name: 'Рондония',
      country: 'Бразилия',
      lat: -10.9,
      lon: -62.8,
      description: 'Устойчивая вырубка леса под сельхозугодья, 2021–2022.',
    ),
  ];

  final Map<String, List<NdviPoint>> _timeseries = {};
  final Map<String, List<Anomaly>> _anomalies = {};

  final _rand = Random(42);

  void _generateAll() {
    final now = DateTime.now();
    final start = DateTime(now.year - 2, now.month, 1);

    for (final region in _regions) {
      final points = <NdviPoint>[];
      for (int m = 0; m < 24; m++) {
        final date = DateTime(start.year, start.month + m, 15);
        final seasonal = 0.55 + 0.2 * sin((date.month / 12) * 2 * pi);
        final noise = (_rand.nextDouble() - 0.5) * 0.03;
        double ndvi = seasonal + noise;
        double normMean = seasonal;
        const normStd = 0.06;

        ndvi += _anomalyOffset(region.id, m);

        points.add(NdviPoint(
          date: date,
          ndvi: ndvi.clamp(0.02, 0.95),
          normMean: normMean.clamp(0.05, 0.9),
          normStd: normStd,
        ));
      }
      _timeseries[region.id] = points;
      _anomalies[region.id] = _buildAnomalies(region.id, points);
    }
  }

  /// Injects a scripted anomaly window per demo region into month index [m].
  double _anomalyOffset(String regionId, int m) {
    switch (regionId) {
      case 'mekong-delta':
        // Gradual drought onset around month 14, slow partial recovery.
        if (m >= 14 && m <= 19) {
          final depth = [0.05, 0.15, 0.28, 0.32, 0.24, 0.12][m - 14];
          return -depth;
        }
        return 0;
      case 'paradise-ca':
        // Sudden fire at month 10, sharp drop then slow regrowth.
        if (m == 10) return -0.42;
        if (m == 11) return -0.38;
        if (m >= 12 && m <= 17) {
          return -0.3 + (m - 12) * 0.035;
        }
        return 0;
      case 'rondonia-br':
        // Deforestation: permanent step-down starting month 8, deepening.
        if (m >= 8) {
          final monthsIn = m - 8;
          return -(0.15 + min(monthsIn * 0.015, 0.25));
        }
        return 0;
      default:
        return 0;
    }
  }

  List<Anomaly> _buildAnomalies(String regionId, List<NdviPoint> points) {
    final anomalies = <Anomaly>[];
    bool inRun = false;
    int runStart = 0;

    for (int i = 0; i < points.length; i++) {
      final anomalous = points[i].isAnomalous;
      if (anomalous && !inRun) {
        inRun = true;
        runStart = i;
      }
      if (!anomalous && inRun) {
        anomalies.add(_anomalyFor(regionId, points, runStart, i - 1));
        inRun = false;
      }
    }
    if (inRun) {
      anomalies.add(_anomalyFor(regionId, points, runStart, points.length - 1));
    }
    return anomalies;
  }

  Anomaly _anomalyFor(
    String regionId,
    List<NdviPoint> points,
    int startIdx,
    int endIdx,
  ) {
    final worst = points
        .sublist(startIdx, endIdx + 1)
        .reduce((a, b) => a.zScore < b.zScore ? a : b);

    late AnomalyType type;
    late String explanation;
    switch (regionId) {
      case 'mekong-delta':
        type = AnomalyType.drought;
        explanation =
            'Продолжительное отклонение NDVI ниже нормы совпадает с сезоном '
            'муссонной засухи — индекс восстанавливается медленно, что '
            'типично для нехватки влаги, а не единовременного события.';
        break;
      case 'paradise-ca':
        type = AnomalyType.fire;
        explanation =
            'Резкое однократное падение NDVI на 0.3-0.4 за один месяц с '
            'последующим постепенным ростом — характерная сигнатура пожара '
            'и последующей регенерации растительности.';
        break;
      case 'rondonia-br':
        type = AnomalyType.deforestation;
        explanation =
            'Ступенчатое и не восстанавливающееся снижение NDVI, '
            'усиливающееся со временем — признак систематической вырубки, '
            'а не сезонного стресса.';
        break;
      default:
        type = AnomalyType.unknown;
        explanation = 'Отклонение NDVI от климатической нормы.';
    }

    return Anomaly(
      id: '$regionId-${points[startIdx].date.toIso8601String()}',
      regionId: regionId,
      startDate: points[startIdx].date,
      endDate: points[endIdx].date,
      type: type,
      severity: worst.zScore.abs() >= 4
          ? AnomalySeverity.high
          : worst.zScore.abs() >= 2.5
              ? AnomalySeverity.medium
              : AnomalySeverity.low,
      deviation: worst.ndvi - worst.normMean,
      explanation: explanation,
    );
  }

  @override
  Future<List<Region>> getRegions() async => _regions;

  @override
  Future<List<NdviPoint>> getTimeseries(String regionId) async =>
      _timeseries[regionId] ?? [];

  @override
  Future<List<Anomaly>> getAnomalies({String? regionId}) async {
    if (regionId != null) return _anomalies[regionId] ?? [];
    return _anomalies.values.expand((a) => a).toList();
  }

  @override
  String tileUrlTemplate(DateTime date) {
    // No real NDVI raster tiles in mock mode; the map screen falls back to
    // a plain basemap and renders NDVI as coloured region markers instead.
    return '';
  }
}
