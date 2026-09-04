import 'dart:convert';

import 'package:http/http.dart' as http;
import 'package:latlong2/latlong.dart';

import '../models/anomaly.dart';
import '../models/demo_area.dart';
import '../models/ndvi_point.dart';
import '../models/ndvi_polygon.dart';
import 'vegetation_data_service.dart';

/// Работает с реальным бэкендом, когда он появится. Соответствует
/// контракту в [VegetationDataService]:
///   GET  {baseUrl}/polygons
///   POST {baseUrl}/polygons/custom
///   GET  {baseUrl}/timeseries/{anon_polygon_id}
///   GET  {baseUrl}/anomalies?polygon_id={id}
class HttpVegetationDataService implements VegetationDataService {
  HttpVegetationDataService({required this.baseUrl, http.Client? client})
      : _client = client ?? http.Client();

  final String baseUrl;
  final http.Client _client;

  Uri _uri(String path, [Map<String, String>? query]) =>
      Uri.parse('$baseUrl$path').replace(queryParameters: query);

  @override
  List<DemoArea> getDemoAreas() => const [];

  @override
  Future<List<NdviPolygon>> getPolygons() async {
    final res = await _client.get(_uri('/polygons'));
    _checkOk(res);
    final list = jsonDecode(res.body) as List;
    return list
        .map((e) => NdviPolygon.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  @override
  Future<NdviPolygon> submitCustomPolygon(List<LatLng> points) async {
    final res = await _client.post(
      _uri('/polygons/custom'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({
        'points': points.map((p) => [p.latitude, p.longitude]).toList(),
      }),
    );
    _checkOk(res);
    return NdviPolygon.fromJson(jsonDecode(res.body) as Map<String, dynamic>);
  }

  @override
  Future<List<NdviPoint>> getTimeseries(String polygonId) async {
    final res = await _client.get(_uri('/timeseries/$polygonId'));
    _checkOk(res);
    final list = jsonDecode(res.body) as List;
    return list
        .map((e) => NdviPoint.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  @override
  Future<List<Anomaly>> getAnomalies({String? polygonId}) async {
    final res = await _client.get(
      _uri('/anomalies', polygonId != null ? {'polygon_id': polygonId} : null),
    );
    _checkOk(res);
    final list = jsonDecode(res.body) as List;
    return list.map((e) => Anomaly.fromJson(e as Map<String, dynamic>)).toList();
  }

  void _checkOk(http.Response res) {
    if (res.statusCode < 200 || res.statusCode >= 300) {
      throw Exception('API error ${res.statusCode}: ${res.body}');
    }
  }
}
