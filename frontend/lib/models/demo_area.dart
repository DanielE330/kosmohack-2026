/// Именованная точка только для наведения камеры карты и группировки
/// нескольких демо-полигонов на питче — не часть схемы данных соревнования
/// (там есть только анонимные полигоны с `anon_polygon_id`).
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
