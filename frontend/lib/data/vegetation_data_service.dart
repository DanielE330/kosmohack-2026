import 'package:latlong2/latlong.dart';

import '../models/anomaly.dart';
import '../models/demo_area.dart';
import '../models/map_info.dart';
import '../models/ndvi_point.dart';
import '../models/ndvi_polygon.dart';

/// Контракт, соответствующий реальной схеме данных соревнования (по ТЗ):
///   GET    /polygons?region={bbox}           -> открытые контуры AOI (OSM/ESA WorldCereal);
///                                                с `region` — автопоиск контуров в указанной области
///   POST   /polygons/custom {points}         -> регистрирует нарисованный пользователем AOI, возвращает его id
///   DELETE /polygons/{id}                    -> удаляет полигон из набора пользователя
///   GET    /timeseries/{anon_polygon_id}      -> `List<NdviPoint>` (primary_ndvi + восстановление пропусков)
///   GET    /anomalies?polygon_id={id}         -> `List<Anomaly>` (диапазоны Z-score)
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
  /// `true` для реального бэкенда — там создание/изменение/удаление
  /// своего полигона требует входа (JWT). Мок-демо не требует авторизации
  /// вообще, чтобы посетитель мог сразу попробовать сервис.
  bool get requiresAuth;

  /// Только для демо: именованные точки для наведения камеры карты и
  /// группировки полигонов.
  List<DemoArea> getDemoAreas();

  /// [mapId] — только полигоны этой карты (нужен доступ); без него — все,
  /// что видно текущему пользователю (открытые + свои/расшаренные карты).
  Future<List<NdviPolygon>> getPolygons({int? mapId});

  /// [mapId] — на какую карту добавить; без него — личная карта
  /// пользователя (создаётся автоматически при первом обращении).
  Future<NdviPolygon> submitCustomPolygon(List<LatLng> points, {String? label, int? mapId});

  /// Карты, доступные текущему пользователю (свои + куда пригласили) —
  /// см. критерий про совместную работу/шаринг.
  Future<List<MapInfo>> getMaps();
  Future<MapInfo> createMap(String name);
  Future<List<MapMemberInfo>> getMapMembers(int mapId);
  Future<MapMemberInfo> inviteToMap(int mapId, {required String email, required MapRole role});
  Future<void> removeMapMember(int mapId, int userId);

  /// Update своего полигона: любой параметр — `null`, если не меняется.
  Future<NdviPolygon> updatePolygon(
    String polygonId, {
    String? label,
    String? cropType,
    List<LatLng>? points,
  });

  Future<void> deletePolygon(String polygonId);

  /// Автопоиск доступных сельхозконтуров в указанном bbox — критерий
  /// «Управление полигонами» требует это как отдельную от ручного рисования
  /// возможность (см. tasks/backend.md).
  Future<List<NdviPolygon>> findPolygonsInRegion({
    required double minLat,
    required double minLon,
    required double maxLat,
    required double maxLon,
  });

  Future<List<NdviPoint>> getTimeseries(String polygonId);
  Future<List<Anomaly>> getAnomalies({String? polygonId});
}
