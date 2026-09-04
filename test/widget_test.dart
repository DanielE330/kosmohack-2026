import 'package:flutter_test/flutter_test.dart';

import 'package:kosmohack_app/data/mock_vegetation_data_service.dart';
import 'package:kosmohack_app/models/anomaly.dart';

void main() {
  late MockVegetationDataService service;

  setUp(() {
    service = MockVegetationDataService();
  });

  test('exposes the three demo regions used for the pitch', () async {
    final regions = await service.getRegions();
    expect(regions.map((r) => r.id).toSet(), {
      'mekong-delta',
      'paradise-ca',
      'rondonia-br',
    });
  });

  test('each demo region has a 24-month NDVI timeseries', () async {
    final regions = await service.getRegions();
    for (final region in regions) {
      final points = await service.getTimeseries(region.id);
      expect(points.length, 24);
      expect(points.every((p) => p.ndvi >= 0 && p.ndvi <= 1), isTrue);
    }
  });

  test('each demo region has at least one detected anomaly', () async {
    final regions = await service.getRegions();
    for (final region in regions) {
      final anomalies = await service.getAnomalies(regionId: region.id);
      expect(anomalies, isNotEmpty,
          reason: '${region.id} must reliably show an anomaly for the demo');
    }
  });

  test('anomaly types match the scripted event per region', () async {
    final fireAnomalies =
        await service.getAnomalies(regionId: 'paradise-ca');
    expect(fireAnomalies.first.type, AnomalyType.fire);

    final droughtAnomalies =
        await service.getAnomalies(regionId: 'mekong-delta');
    expect(droughtAnomalies.first.type, AnomalyType.drought);

    final deforestationAnomalies =
        await service.getAnomalies(regionId: 'rondonia-br');
    expect(deforestationAnomalies.first.type, AnomalyType.deforestation);
  });
}
