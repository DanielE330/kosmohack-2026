import 'package:latlong2/latlong.dart';

import '../models/anomaly.dart';
import '../models/demo_area.dart';
import '../models/ndvi_point.dart';
import '../models/ndvi_polygon.dart';

/// Contract matching the competition's actual data spec (per the task PDF):
///   GET  /polygons                         -> open-source AOI contours (OSM/ESA WorldCereal)
///   POST /polygons/custom {points}         -> registers a user-drawn AOI, returns its id
///   GET  /timeseries/{anon_polygon_id}      -> `List<NdviPoint>` (primary_ndvi + gap-fill)
///   GET  /anomalies?polygon_id={id}         -> `List<Anomaly>` (Z-score bands)
///
/// The competition also requires a *separate* technical batch-inference
/// entry point (`private_features.csv` -> `submission.csv`) — that is a
/// backend/ML deliverable, not something this Flutter app drives.
///
/// [MockVegetationDataService] fakes all of this so the UI can be built and
/// demoed before the backend is ready; [HttpVegetationDataService] talks to
/// the real API once it's up. Swapping the implementation in main.dart is
/// the only change needed to go from mocks to the live backend.
abstract class VegetationDataService {
  /// Demo-only: named places to frame the map camera and group polygons.
  List<DemoArea> getDemoAreas();

  Future<List<NdviPolygon>> getPolygons();
  Future<NdviPolygon> submitCustomPolygon(List<LatLng> points);
  Future<List<NdviPoint>> getTimeseries(String polygonId);
  Future<List<Anomaly>> getAnomalies({String? polygonId});
}
