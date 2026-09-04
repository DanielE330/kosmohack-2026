import '../models/anomaly.dart';
import '../models/ndvi_point.dart';
import '../models/region.dart';

/// Contract the whole team agreed on for the backend API:
///   GET /tiles/{z}/{x}/{y}.png?date=YYYY-MM-DD  -> NDVI raster tile
///   GET /timeseries/{region}                    -> `List<NdviPoint>`
///   GET /anomalies?region={region}              -> `List<Anomaly>`
///
/// [MockVegetationDataService] fakes this so the UI can be built before the
/// backend is ready; [HttpVegetationDataService] talks to the real API once
/// it's up. Swapping the implementation in main.dart is the only change
/// needed to go from mocks to the live backend.
abstract class VegetationDataService {
  Future<List<Region>> getRegions();
  Future<List<NdviPoint>> getTimeseries(String regionId);
  Future<List<Anomaly>> getAnomalies({String? regionId});

  /// URL template for the NDVI tile layer at a given date, in the
  /// `{z}/{x}/{y}` placeholder format `flutter_map`'s TileLayer expects.
  String tileUrlTemplate(DateTime date);
}
