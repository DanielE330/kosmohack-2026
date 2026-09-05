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
///   GET    {baseUrl}/polygons?region={bbox}
///   POST   {baseUrl}/polygons/custom          (нужен Authorization)
///   PUT    {baseUrl}/polygons/{id}            (нужен Authorization)
///   DELETE {baseUrl}/polygons/{id}            (нужен Authorization)
///   GET    {baseUrl}/timeseries/{anon_polygon_id}
///   GET    {baseUrl}/anomalies?polygon_id={id}
///
/// [tokenProvider] читает текущий JWT из `AuthRepository` на момент
/// каждого запроса (а не один раз при создании) — так что логин/логаут
/// подхватываются без пересоздания сервиса.
class HttpVegetationDataService implements VegetationDataService {
  HttpVegetationDataService({
    required this.baseUrl,
    this.tokenProvider,
    http.Client? client,
  }) : _client = client ?? http.Client();

  final String baseUrl;
  final String? Function()? tokenProvider;
  final http.Client _client;

  Uri _uri(String path, [Map<String, String>? query]) =>
      Uri.parse('$baseUrl$path').replace(queryParameters: query);

  Map<String, String> _authHeaders({bool json = false}) {
    final headers = <String, String>{if (json) 'Content-Type': 'application/json'};
    final token = tokenProvider?.call();
    if (token != null) headers['Authorization'] = 'Bearer $token';
    return headers;
  }

  @override
  bool get requiresAuth => true;

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
      headers: _authHeaders(json: true),
      body: jsonEncode({
        'points': points.map((p) => [p.latitude, p.longitude]).toList(),
      }),
    );
    _checkOk(res);
    return NdviPolygon.fromJson(jsonDecode(res.body) as Map<String, dynamic>);
  }

  @override
  Future<NdviPolygon> updatePolygon(
    String polygonId, {
    String? label,
    String? cropType,
    List<LatLng>? points,
  }) async {
    final res = await _client.put(
      _uri('/polygons/$polygonId'),
      headers: _authHeaders(json: true),
      body: jsonEncode({
        'label': ?label,
        'crop_type': ?cropType,
        if (points != null) 'points': points.map((p) => [p.latitude, p.longitude]).toList(),
      }),
    );
    _checkOk(res);
    return NdviPolygon.fromJson(jsonDecode(res.body) as Map<String, dynamic>);
  }

  @override
  Future<void> deletePolygon(String polygonId) async {
    final res = await _client.delete(_uri('/polygons/$polygonId'), headers: _authHeaders());
    _checkOk(res);
  }

  @override
  Future<List<NdviPolygon>> findPolygonsInRegion({
    required double minLat,
    required double minLon,
    required double maxLat,
    required double maxLon,
  }) async {
    final res = await _client.get(_uri('/polygons', {
      'region': '$minLat,$minLon,$maxLat,$maxLon',
    }));
    _checkOk(res);
    final list = jsonDecode(res.body) as List;
    return list
        .map((e) => NdviPolygon.fromJson(e as Map<String, dynamic>))
        .toList();
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
