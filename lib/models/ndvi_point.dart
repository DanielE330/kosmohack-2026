/// One point of a region's NDVI time series, together with the expected
/// climate-norm band (mean +/- std across previous years for that day of year)
/// so the UI can plot "actual vs normal" and shade the deviation.
class NdviPoint {
  final DateTime date;
  final double ndvi;
  final double normMean;
  final double normStd;

  const NdviPoint({
    required this.date,
    required this.ndvi,
    required this.normMean,
    required this.normStd,
  });

  double get zScore => normStd == 0 ? 0 : (ndvi - normMean) / normStd;
  bool get isAnomalous => zScore.abs() >= 1.5;

  factory NdviPoint.fromJson(Map<String, dynamic> json) {
    return NdviPoint(
      date: DateTime.parse(json['date'] as String),
      ndvi: (json['ndvi'] as num).toDouble(),
      normMean: (json['norm_mean'] as num).toDouble(),
      normStd: (json['norm_std'] as num).toDouble(),
    );
  }

  Map<String, dynamic> toJson() => {
        'date': date.toIso8601String(),
        'ndvi': ndvi,
        'norm_mean': normMean,
        'norm_std': normStd,
      };
}
