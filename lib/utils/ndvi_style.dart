import 'package:flutter/material.dart';

import '../models/anomaly.dart';

/// Maps an NDVI value in [0, 1] to a colour on a red -> yellow -> green
/// vegetation-health scale, matching the palette used on the map overlay
/// and in the timeseries chart so both stay visually consistent.
Color ndviColor(double ndvi) {
  final t = ndvi.clamp(0.0, 1.0);
  if (t < 0.35) {
    return Color.lerp(const Color(0xFFB3261E), const Color(0xFFE8A33D), t / 0.35)!;
  }
  return Color.lerp(const Color(0xFFE8A33D), const Color(0xFF2E7D32), (t - 0.35) / 0.65)!;
}

IconData anomalyIcon(AnomalyType type) {
  switch (type) {
    case AnomalyType.fire:
      return Icons.local_fire_department;
    case AnomalyType.drought:
      return Icons.water_drop_outlined;
    case AnomalyType.deforestation:
      return Icons.forest_outlined;
    case AnomalyType.flood:
      return Icons.flood_outlined;
    case AnomalyType.unknown:
      return Icons.warning_amber_rounded;
  }
}

String anomalyTypeLabel(AnomalyType type) {
  switch (type) {
    case AnomalyType.fire:
      return 'Пожар';
    case AnomalyType.drought:
      return 'Засуха';
    case AnomalyType.deforestation:
      return 'Вырубка';
    case AnomalyType.flood:
      return 'Паводок';
    case AnomalyType.unknown:
      return 'Аномалия';
  }
}

Color severityColor(AnomalySeverity severity) {
  switch (severity) {
    case AnomalySeverity.low:
      return const Color(0xFFE8A33D);
    case AnomalySeverity.medium:
      return const Color(0xFFE8630A);
    case AnomalySeverity.high:
      return const Color(0xFFB3261E);
  }
}

String severityLabel(AnomalySeverity severity) {
  switch (severity) {
    case AnomalySeverity.low:
      return 'Низкая';
    case AnomalySeverity.medium:
      return 'Средняя';
    case AnomalySeverity.high:
      return 'Высокая';
  }
}
