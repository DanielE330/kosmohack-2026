/// A named place used only to frame the map camera and group a handful of
/// demo polygons for the pitch — not part of the competition's data schema
/// (which only knows anonymous `anon_polygon_id` field polygons).
class DemoArea {
  final String id;
  final String name;
  final String country;
  final double lat;
  final double lon;
  final String description;

  const DemoArea({
    required this.id,
    required this.name,
    required this.country,
    required this.lat,
    required this.lon,
    required this.description,
  });
}
