import 'ndvi_point.dart';

/// Only the two non-normal [NdviStatus] bands ever form an [Anomaly] period.
typedef AnomalySeverity = NdviStatus;

/// A contiguous run of dates whose Z-score fell below -1 (suppression) or
/// -2 (critical) — see [ndviStatusForZ]. [severity] is the worst status
/// reached anywhere in the run.
class Anomaly {
  final String id;
  final String polygonId;
  final DateTime startDate;
  final DateTime endDate;
  final AnomalySeverity severity;
  final double minZScore;
  /// Deviation from the climate norm, e.g. -0.35 means NDVI dropped 0.35
  /// below the expected seasonal value.
  final double deviation;
  final String explanation;

  const Anomaly({
    required this.id,
    required this.polygonId,
    required this.startDate,
    required this.endDate,
    required this.severity,
    required this.minZScore,
    required this.deviation,
    required this.explanation,
  });

  factory Anomaly.fromJson(Map<String, dynamic> json) {
    return Anomaly(
      id: json['id'] as String,
      polygonId: json['anon_polygon_id'] as String,
      startDate: DateTime.parse(json['start_date'] as String),
      endDate: DateTime.parse(json['end_date'] as String),
      severity: NdviStatus.values.firstWhere(
        (s) => s.name == json['severity'],
        orElse: () => NdviStatus.suppression,
      ),
      minZScore: (json['min_z_score'] as num).toDouble(),
      deviation: (json['deviation'] as num).toDouble(),
      explanation: json['explanation'] as String? ?? '',
    );
  }

  Map<String, dynamic> toJson() => {
        'id': id,
        'anon_polygon_id': polygonId,
        'start_date': startDate.toIso8601String(),
        'end_date': endDate.toIso8601String(),
        'severity': severity.name,
        'min_z_score': minZScore,
        'deviation': deviation,
        'explanation': explanation,
      };
}
