import 'package:flutter/material.dart';

import '../models/ndvi_point.dart';

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

/// Colour/label for the three Z-score bands defined by the competition spec:
/// Z >= -1 normal, -2 <= Z < -1 suppression, Z < -2 critical.
Color statusColor(NdviStatus status) {
  switch (status) {
    case NdviStatus.normal:
      return const Color(0xFF2E7D32);
    case NdviStatus.suppression:
      return const Color(0xFFE8630A);
    case NdviStatus.critical:
      return const Color(0xFFB3261E);
  }
}

String statusLabel(NdviStatus status) {
  switch (status) {
    case NdviStatus.normal:
      return 'Штатное развитие';
    case NdviStatus.suppression:
      return 'Угнетение биомассы';
    case NdviStatus.critical:
      return 'Критическая аномалия';
  }
}
