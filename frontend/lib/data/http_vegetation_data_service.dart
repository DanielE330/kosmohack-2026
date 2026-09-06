import 'dart:convert';

import 'package:http/http.dart' as http;
import 'package:latlong2/latlong.dart';

import '../models/anomaly.dart';
import '../models/demo_area.dart';
import '../models/map_info.dart';
import '../models/ndvi_point.dart';
import '../models/ndvi_polygon.dart';
import 'api_exception.dart';
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
  Future<List<NdviPolygon>> getPolygons({int? mapId}) async {
    // С токеном — иначе бэкенд отдаёт только открытые (без карты) сидовые
    // полигоны датасета: полигоны на своих/расшаренных картах видны
    // только тому, у кого есть доступ (см. backend/app/api/routes/polygons.py).
    final res = await _client.get(
      _uri('/polygons', mapId != null ? {'map_id': '$mapId'} : null),
      headers: _authHeaders(),
    );
    _checkOk(res);
    final list = jsonDecode(res.body) as List;
    return list
        .map((e) => NdviPolygon.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  @override
  Future<NdviPolygon> getPolygon(String polygonId, {String? shareToken}) async {
    // Именно один полигон по id, а не поиск в списке `GET /polygons`:
    // список отдаёт только видимое текущему пользователю, поэтому по
    // присланной ссылке участок с чужой карты в нём не находился и экран
    // показывал «Полигон не найден». Здесь бэкенд сам решает по правам —
    // и понимает токен ссылки «поделиться» для тех, кто не вошёл.
    final res = await _client.get(
      _uri('/polygons/$polygonId', shareToken != null ? {'share': shareToken} : null),
      headers: _authHeaders(),
    );
    _checkOk(res);
    return NdviPolygon.fromJson(jsonDecode(res.body) as Map<String, dynamic>);
  }

  @override
  Future<String?> createShareLinkToken(String polygonId) async {
    final res = await _client.post(_uri('/polygons/$polygonId/share-link'), headers: _authHeaders());
    _checkOk(res);
    return (jsonDecode(res.body) as Map<String, dynamic>)['share_token'] as String?;
  }

  @override
  Future<NdviPolygon> submitCustomPolygon(List<LatLng> points, {String? label, int? mapId}) async {
    final res = await _client.post(
      _uri('/polygons/custom'),
      headers: _authHeaders(json: true),
      body: jsonEncode({
        'points': points.map((p) => [p.latitude, p.longitude]).toList(),
        if (label != null && label.isNotEmpty) 'label': label,
        'map_id': ?mapId,
      }),
    );
    _checkOk(res);
    return NdviPolygon.fromJson(jsonDecode(res.body) as Map<String, dynamic>);
  }

  @override
  Future<List<MapInfo>> getMaps() async {
    final res = await _client.get(_uri('/maps'), headers: _authHeaders());
    _checkOk(res);
    final list = jsonDecode(res.body) as List;
    return list.map((e) => MapInfo.fromJson(e as Map<String, dynamic>)).toList();
  }

  @override
  Future<MapInfo> createMap(String name) async {
    final res = await _client.post(
      _uri('/maps'),
      headers: _authHeaders(json: true),
      body: jsonEncode({'name': name}),
    );
    _checkOk(res);
    return MapInfo.fromJson(jsonDecode(res.body) as Map<String, dynamic>);
  }

  @override
  Future<List<MapMemberInfo>> getMapMembers(int mapId) async {
    final res = await _client.get(_uri('/maps/$mapId/members'), headers: _authHeaders());
    _checkOk(res);
    final list = jsonDecode(res.body) as List;
    return list.map((e) => MapMemberInfo.fromJson(e as Map<String, dynamic>)).toList();
  }

  @override
  Future<MapMemberInfo> inviteToMap(int mapId, {required String email, required MapRole role}) async {
    final res = await _client.post(
      _uri('/maps/$mapId/invite'),
      headers: _authHeaders(json: true),
      body: jsonEncode({'email': email, 'role': role.name}),
    );
    _checkOk(res);
    return MapMemberInfo.fromJson(jsonDecode(res.body) as Map<String, dynamic>);
  }

  @override
  Future<void> removeMapMember(int mapId, int userId) async {
    final res = await _client.delete(_uri('/maps/$mapId/members/$userId'), headers: _authHeaders());
    _checkOk(res);
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
    final res = await _client.get(
      _uri('/polygons', {'region': '$minLat,$minLon,$maxLat,$maxLon'}),
      headers: _authHeaders(),
    );
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
  Future<PolygonsWithTimeseries> getPolygonsWithTimeseries({int? mapId}) async {
    // Один запрос вместо getPolygons + Future.wait(getTimeseries) на каждый —
    // см. backend GET /polygons/with-timeseries.
    final res = await _client.get(
      _uri('/polygons/with-timeseries', mapId != null ? {'map_id': '$mapId'} : null),
      headers: _authHeaders(),
    );
    _checkOk(res);
    final list = jsonDecode(res.body) as List;
    final polygons = <NdviPolygon>[];
    final timeseries = <String, List<NdviPoint>>{};
    for (final item in list) {
      final json = item as Map<String, dynamic>;
      final polygon = NdviPolygon.fromJson(json);
      polygons.add(polygon);
      timeseries[polygon.id] = (json['timeseries'] as List)
          .map((e) => NdviPoint.fromJson(e as Map<String, dynamic>))
          .toList();
    }
    return (polygons: polygons, timeseries: timeseries);
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

  @override
  Future<ExportedFile?> exportExcel(List<String> polygonIds) async {
    if (polygonIds.isEmpty) return null;
    // Один участок — книга .xlsx, несколько — zip с книгой на каждый
    // (см. backend/app/api/routes/export.py).
    final single = polygonIds.length == 1;
    final uri = single
        ? _uri('/export/polygon/${Uri.encodeComponent(polygonIds.single)}.xlsx')
        : _uri('/export/polygons.zip', {'ids': polygonIds.join(',')});
    // Скачиваем обычным GET с заголовком Authorization и отдаём blob, а не
    // открываем URL в новой вкладке: window.open заголовки не передаёт, а
    // токен в query-параметре утёк бы в историю браузера и логи прокси.
    final res = await _client.get(uri, headers: _authHeaders());
    _checkOk(res);
    final fallback = single ? 'skytime-${polygonIds.single}.xlsx' : 'skytime-report.zip';
    return (
      filename: _filenameFromHeaders(res.headers) ?? fallback,
      bytes: res.bodyBytes,
      mimeType: res.headers['content-type'] ??
          (single
              ? 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
              : 'application/zip'),
    );
  }

  /// Имя файла из `Content-Disposition`. Оно кириллическое, поэтому
  /// бэкенд отдаёт его в RFC 5987-форме `filename*=UTF-8''%D0%9E...` —
  /// её и разбираем в первую очередь, обычный `filename="..."` остаётся
  /// запасным вариантом.
  String? _filenameFromHeaders(Map<String, String> headers) {
    final disposition = headers['content-disposition'];
    if (disposition == null) return null;
    final encoded = RegExp(r"filename\*=UTF-8''([^;]+)").firstMatch(disposition);
    if (encoded != null) {
      try {
        return Uri.decodeComponent(encoded.group(1)!.trim());
      } catch (_) {
        // Битая процентная кодировка — не повод ронять скачивание.
      }
    }
    final plain = RegExp(r'filename="([^"]+)"').firstMatch(disposition);
    return plain?.group(1);
  }

  void _checkOk(http.Response res) {
    if (res.statusCode < 200 || res.statusCode >= 300) {
      throw ApiException(res.statusCode, _detail(res));
    }
  }

  /// FastAPI кладёт человекочитаемую причину в `detail` — показываем её,
  /// а не сырой JSON: тексты ошибок на бэкенде уже написаны для человека.
  String _detail(http.Response res) {
    try {
      final body = jsonDecode(res.body);
      if (body is Map && body['detail'] is String) return body['detail'] as String;
    } catch (_) {
      // Не JSON (например, HTML от прокси) — покажем как есть.
    }
    return res.body;
  }
}
