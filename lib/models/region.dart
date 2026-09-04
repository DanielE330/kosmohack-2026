class Region {
  final String id;
  final String name;
  final String country;
  final double lat;
  final double lon;
  /// Short human description of why this region was picked for the demo.
  final String description;

  const Region({
    required this.id,
    required this.name,
    required this.country,
    required this.lat,
    required this.lon,
    required this.description,
  });

  factory Region.fromJson(Map<String, dynamic> json) {
    return Region(
      id: json['id'] as String,
      name: json['name'] as String,
      country: json['country'] as String,
      lat: (json['lat'] as num).toDouble(),
      lon: (json['lon'] as num).toDouble(),
      description: json['description'] as String? ?? '',
    );
  }

  Map<String, dynamic> toJson() => {
        'id': id,
        'name': name,
        'country': country,
        'lat': lat,
        'lon': lon,
        'description': description,
      };
}
