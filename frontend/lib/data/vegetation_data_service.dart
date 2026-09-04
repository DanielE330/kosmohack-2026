import 'package:latlong2/latlong.dart';

import '../models/anomaly.dart';
import '../models/demo_area.dart';
import '../models/ndvi_point.dart';
import '../models/ndvi_polygon.dart';

/// Контракт, соответствующий реальной схеме данных соревнования (по ТЗ):
///   GET  /polygons                         -> открытые контуры AOI (OSM/ESA WorldCereal)
///   POST /polygons/custom {points}         -> регистрирует нарисованный пользователем AOI, возвращает его id
///   GET  /timeseries/{anon_polygon_id}      -> `List<NdviPoint>` (primary_ndvi + восстановление пропусков)
///   GET  /anomalies?polygon_id={id}         -> `List<Anomaly>` (диапазоны Z-score)
///
/// Соревнование также требует *отдельную* точку входа для технического
/// batch-инференса (`private_features.csv` -> `submission.csv`) — это
/// зона ответственности бэкенда/ML, не этого Flutter-приложения.
///
/// [MockVegetationDataService] эмулирует всё это, чтобы UI можно было
/// строить и показывать до готовности бэкенда; [HttpVegetationDataService]
/// работает с реальным API, когда он поднимется. Замена реализации в
/// main.dart — единственное, что нужно поменять для перехода с моков на
/// живой бэкенд.
abstract class VegetationDataService {
  /// Только для демо: именованные точки для наведения камеры карты и
  /// группировки полигонов.
  List<DemoArea> getDemoAreas();

  Future<List<NdviPolygon>> getPolygons();
  Future<NdviPolygon> submitCustomPolygon(List<LatLng> points);
  Future<List<NdviPoint>> getTimeseries(String polygonId);
  Future<List<Anomaly>> getAnomalies({String? polygonId});
}
