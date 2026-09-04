import 'package:flutter/material.dart';

import '../models/ndvi_point.dart';

/// Переводит значение NDVI из [0, 1] в цвет по шкале
/// красный → жёлтый → зелёный (здоровье растительности) — та же палитра,
/// что на карте и на графике временного ряда, для визуальной консистентности.
Color ndviColor(double ndvi) {
  final t = ndvi.clamp(0.0, 1.0);
  if (t < 0.35) {
    return Color.lerp(const Color(0xFFB3261E), const Color(0xFFE8A33D), t / 0.35)!;
  }
  return Color.lerp(const Color(0xFFE8A33D), const Color(0xFF2E7D32), (t - 0.35) / 0.65)!;
}

/// Цвет/подпись для трёх диапазонов Z-score из ТЗ:
/// Z >= -1 штатно, -2 <= Z < -1 угнетение, Z < -2 критическая аномалия.
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
