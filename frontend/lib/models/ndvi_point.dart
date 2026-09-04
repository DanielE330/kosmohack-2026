/// Пороги классификации аномалий — ровно как в глоссарии ТЗ ("МЕТРИКА
/// ОЦЕНКИ" / "ТЕОРЕТИЧЕСКАЯ БАЗА" в PDF): Z >= -1 — штатное развитие,
/// -2 <= Z < -1 — угнетение биомассы, Z < -2 — критическая аномалия.
/// Аномальным считается только отрицательное отклонение.
enum NdviStatus { normal, suppression, critical }

NdviStatus ndviStatusForZ(double z) {
  if (z < -2) return NdviStatus.critical;
  if (z < -1) return NdviStatus.suppression;
  return NdviStatus.normal;
}

/// Одна строка временного ряда соревнования по полигону и дате
/// (`anon_polygon_id` + `date`). [observedNdvi] — реальное значение
/// `primary_ndvi`, если на эту дату есть пригодное спутниковое наблюдение;
/// `null` для пропусков (включая специально скрытые контрольные точки
/// `is_synthetic_gap`) — тогда [restoredNdvi] несёт восстановленное/
/// предсказанное значение, которое реально рисуется на графике.
class NdviPoint {
  final DateTime date;
  final double? observedNdvi;
  final double restoredNdvi;
  final bool isSyntheticGap;
  final double climatologyMean;
  final double climatologyStd;
  final String cropType;

  const NdviPoint({
    required this.date,
    required this.observedNdvi,
    required this.restoredNdvi,
    required this.isSyntheticGap,
    required this.climatologyMean,
    required this.climatologyStd,
    required this.cropType,
  });

  bool get isRestored => observedNdvi == null;

  /// Значение, которое рисуется на графике и используется для расчёта
  /// аномалий: реальное наблюдение, если оно есть, иначе — восстановленная
  /// оценка.
  double get value => observedNdvi ?? restoredNdvi;

  double get zScore =>
      climatologyStd == 0 ? 0 : (value - climatologyMean) / climatologyStd;

  NdviStatus get status => ndviStatusForZ(zScore);

  factory NdviPoint.fromJson(Map<String, dynamic> json) {
    return NdviPoint(
      date: DateTime.parse(json['date'] as String),
      observedNdvi: (json['primary_ndvi'] as num?)?.toDouble(),
      restoredNdvi: (json['primary_ndvi_pred'] as num).toDouble(),
      isSyntheticGap: json['is_synthetic_gap'] as bool? ?? false,
      climatologyMean: (json['climatology_mean'] as num).toDouble(),
      climatologyStd: (json['climatology_std'] as num).toDouble(),
      cropType: json['crop_type'] as String? ?? 'unknown',
    );
  }

  Map<String, dynamic> toJson() => {
        'date': date.toIso8601String(),
        'primary_ndvi': observedNdvi,
        'primary_ndvi_pred': restoredNdvi,
        'is_synthetic_gap': isSyntheticGap,
        'climatology_mean': climatologyMean,
        'climatology_std': climatologyStd,
        'crop_type': cropType,
      };
}
