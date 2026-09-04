import 'ndvi_point.dart';

/// Период аномалии образуют только два «не штатных» статуса [NdviStatus].
typedef AnomalySeverity = NdviStatus;

/// Непрерывный отрезок дат, на которых Z-score опустился ниже -1
/// (угнетение) или -2 (критическая аномалия) — см. [ndviStatusForZ].
/// [severity] — худший статус, достигнутый где-либо внутри отрезка.
class Anomaly {
  final String id;
  final String polygonId;
  final DateTime startDate;
  final DateTime endDate;
  final AnomalySeverity severity;
  final double minZScore;
  /// Отклонение от климатической нормы, например -0.35 значит, что NDVI
  /// упал на 0.35 ниже ожидаемого сезонного значения.
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
