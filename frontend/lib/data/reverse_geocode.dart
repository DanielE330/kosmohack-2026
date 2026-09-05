import 'dart:convert';

import 'package:http/http.dart' as http;
import 'package:latlong2/latlong.dart';

/// Обратное геокодирование центроида полигона через Nominatim (OSM) —
/// страна/субъект/район для карточки в карусели участков (см.
/// `map_screen.dart`). Кэш в памяти по координатам, округлённым до 3
/// знаков (~100 м) — соседние точки одного и того же поля не долбят API
/// повторными запросами.
///
/// Запрос идёт прямо из браузера пользователя (не с бэкенда), поэтому не
/// задеть тот же сетевой сбой, что у бэкенда с Overpass/Nominatim (см.
/// tasks/backend.md) — тут используется сеть посетителя сайта, а не сервера.
/// Кастомный User-Agent, который требует usage policy Nominatim, браузеры
/// не позволяют выставить из JS/Dart-кода — приемлемо для некоммерческого
/// хакатон-демо с низким трафиком, но не масштабируется на прод-нагрузку.
class ReverseGeocodeResult {
  const ReverseGeocodeResult({this.country, this.state, this.district});

  final String? country;
  final String? state;
  final String? district;

  bool get isEmpty => country == null && state == null && district == null;

  String get shortLabel {
    final parts = [country, state, district].whereType<String>().toList();
    return parts.join(', ');
  }
}

final Map<String, ReverseGeocodeResult> _cache = {};
final Map<String, Future<ReverseGeocodeResult>> _inFlight = {};

String _keyFor(LatLng point) =>
    '${point.latitude.toStringAsFixed(3)},${point.longitude.toStringAsFixed(3)}';

Future<ReverseGeocodeResult> reverseGeocode(LatLng point) {
  final key = _keyFor(point);
  final cached = _cache[key];
  if (cached != null) return Future.value(cached);
  final pending = _inFlight[key];
  if (pending != null) return pending;

  final future = _fetch(point, key);
  _inFlight[key] = future;
  return future;
}

Future<ReverseGeocodeResult> _fetch(LatLng point, String key) async {
  try {
    final uri = Uri.https('nominatim.openstreetmap.org', '/reverse', {
      'format': 'json',
      'lat': '${point.latitude}',
      'lon': '${point.longitude}',
      'zoom': '10',
      'addressdetails': '1',
    });
    final res = await http.get(uri).timeout(const Duration(seconds: 8));
    if (res.statusCode != 200) return const ReverseGeocodeResult();
    final data = jsonDecode(res.body) as Map<String, dynamic>;
    final address = data['address'] as Map<String, dynamic>?;
    if (address == null) return const ReverseGeocodeResult();
    final result = ReverseGeocodeResult(
      country: address['country'] as String?,
      state: address['state'] as String?,
      district: (address['state_district'] ?? address['county'] ?? address['city_district'])
          as String?,
    );
    _cache[key] = result;
    return result;
  } catch (_) {
    // Сеть/парсинг подвели — не критично, карточка просто останется без
    // геоданных (fallback на культуру), не ломаем интерфейс.
    return const ReverseGeocodeResult();
  } finally {
    _inFlight.remove(key);
  }
}
