import 'dart:convert';

import 'package:http/http.dart' as http;

import '../models/anomaly.dart';
import '../models/ndvi_point.dart';
import '../models/region.dart';
import 'vegetation_data_service.dart';

/// Talks to the real FastAPI backend once it's available. Matches the
/// contract agreed with the backend/ML team:
///   GET {baseUrl}/regions
///   GET {baseUrl}/timeseries/{region}
///   GET {baseUrl}/anomalies?region={region}
///   GET {baseUrl}/tiles/{z}/{x}/{y}.png?date=YYYY-MM-DD
class HttpVegetationDataService implements VegetationDataService {
  HttpVegetationDataService({required this.baseUrl, http.Client? client})
      : _client = client ?? http.Client();

  final String baseUrl;
  final http.Client _client;

  Uri _uri(String path, [Map<String, String>? query]) =>
      Uri.parse('$baseUrl$path').replace(queryParameters: query);

  @override
  Future<List<Region>> getRegions() async {
    final res = await _client.get(_uri('/regions'));
    _checkOk(res);
    final list = jsonDecode(res.body) as List;
    return list.map((e) => Region.fromJson(e as Map<String, dynamic>)).toList();
  }

  @override
  Future<List<NdviPoint>> getTimeseries(String regionId) async {
    final res = await _client.get(_uri('/timeseries/$regionId'));
    _checkOk(res);
    final list = jsonDecode(res.body) as List;
    return list
        .map((e) => NdviPoint.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  @override
  Future<List<Anomaly>> getAnomalies({String? regionId}) async {
    final res = await _client.get(
      _uri('/anomalies', regionId != null ? {'region': regionId} : null),
    );
    _checkOk(res);
    final list = jsonDecode(res.body) as List;
    return list.map((e) => Anomaly.fromJson(e as Map<String, dynamic>)).toList();
  }

  @override
  String tileUrlTemplate(DateTime date) {
    final dateStr =
        '${date.year.toString().padLeft(4, '0')}-${date.month.toString().padLeft(2, '0')}-${date.day.toString().padLeft(2, '0')}';
    return '$baseUrl/tiles/{z}/{x}/{y}.png?date=$dateStr';
  }

  void _checkOk(http.Response res) {
    if (res.statusCode < 200 || res.statusCode >= 300) {
      throw Exception('API error ${res.statusCode}: ${res.body}');
    }
  }
}
