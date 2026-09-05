import 'dart:math' as math;

import '../models/ndvi_polygon.dart';

/// Площадь полигона по формуле шнурков в приближении «плоской земли» —
/// точность достаточна для небольших нарисованных участков (не для
/// картографии), метры на градус долготы взяты для широты центроида.
/// Общий helper — используется в личном кабинете, аналитике и отчётах,
/// чтобы площадь считалась везде одинаково.
double polygonAreaHectares(NdviPolygon polygon) {
  final points = polygon.points;
  if (points.length < 3) return 0;
  const metersPerDegLat = 111320.0;
  final centroidLat = points.map((p) => p.latitude).reduce((a, b) => a + b) / points.length;
  final metersPerDegLon = metersPerDegLat * math.cos(centroidLat * math.pi / 180);
  final xy = points.map((p) => (p.longitude * metersPerDegLon, p.latitude * metersPerDegLat)).toList();
  double sum = 0;
  for (var i = 0; i < xy.length; i++) {
    final (x1, y1) = xy[i];
    final (x2, y2) = xy[(i + 1) % xy.length];
    sum += x1 * y2 - x2 * y1;
  }
  return (sum.abs() / 2) / 10000; // м² -> га
}
