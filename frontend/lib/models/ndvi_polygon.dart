import 'package:latlong2/latlong.dart';

/// One agricultural field contour — the unit of selection the spec requires
/// ("AOI / полигон поля"). In the real dataset this is identified only by
/// an anonymous `anon_polygon_id`; [label] is a friendly caption we add for
/// the demo UI, not part of the competition data.
class NdviPolygon {
  final String id;
  final String label;
  final String cropType;
  final String areaId;
  final List<LatLng> points;
  final bool isCustom;

  const NdviPolygon({
    required this.id,
    required this.label,
    required this.cropType,
    required this.areaId,
    required this.points,
    this.isCustom = false,
  });

  LatLng get centroid {
    final lat = points.map((p) => p.latitude).reduce((a, b) => a + b) / points.length;
    final lon = points.map((p) => p.longitude).reduce((a, b) => a + b) / points.length;
    return LatLng(lat, lon);
  }

  factory NdviPolygon.fromJson(Map<String, dynamic> json) {
    return NdviPolygon(
      id: json['anon_polygon_id'] as String,
      label: json['label'] as String? ?? json['anon_polygon_id'] as String,
      cropType: json['crop_type'] as String? ?? 'unknown',
      areaId: json['area_id'] as String? ?? '',
      isCustom: json['is_custom'] as bool? ?? false,
      points: (json['points'] as List)
          .map((p) => LatLng((p[0] as num).toDouble(), (p[1] as num).toDouble()))
          .toList(),
    );
  }

  Map<String, dynamic> toJson() => {
        'anon_polygon_id': id,
        'label': label,
        'crop_type': cropType,
        'area_id': areaId,
        'is_custom': isCustom,
        'points': points.map((p) => [p.latitude, p.longitude]).toList(),
      };
}
