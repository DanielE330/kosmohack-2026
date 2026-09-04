/// Anomaly classification bands exactly as defined by the competition spec's
/// Z-score glossary (see "МЕТРИКА ОЦЕНКИ" / "ТЕОРЕТИЧЕСКАЯ БАЗА" in the task
/// PDF): Z >= -1 is normal development, -2 <= Z < -1 is biomass suppression,
/// Z < -2 is a critical anomaly. Only negative deviation is judged anomalous.
enum NdviStatus { normal, suppression, critical }

NdviStatus ndviStatusForZ(double z) {
  if (z < -2) return NdviStatus.critical;
  if (z < -1) return NdviStatus.suppression;
  return NdviStatus.normal;
}

/// One row of the competition's per-polygon, per-date time series
/// (`anon_polygon_id` + `date`). [observedNdvi] is the real `primary_ndvi`
/// value when a usable satellite observation exists for that date;
/// it's null for gaps (including deliberately hidden `is_synthetic_gap`
/// control points), in which case [restoredNdvi] carries the gap-filled /
/// predicted value the UI actually plots.
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

  /// The value plotted on charts and used for anomaly scoring: the real
  /// observation when present, otherwise the restored estimate.
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
