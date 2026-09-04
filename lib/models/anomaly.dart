enum AnomalyType { drought, fire, deforestation, flood, unknown }

enum AnomalySeverity { low, medium, high }

class Anomaly {
  final String id;
  final String regionId;
  final DateTime startDate;
  final DateTime? endDate;
  final AnomalyType type;
  final AnomalySeverity severity;
  /// Deviation from the climate norm, e.g. -0.35 means NDVI dropped 0.35
  /// below the expected seasonal value.
  final double deviation;
  final String explanation;

  const Anomaly({
    required this.id,
    required this.regionId,
    required this.startDate,
    this.endDate,
    required this.type,
    required this.severity,
    required this.deviation,
    required this.explanation,
  });

  factory Anomaly.fromJson(Map<String, dynamic> json) {
    return Anomaly(
      id: json['id'] as String,
      regionId: json['region_id'] as String,
      startDate: DateTime.parse(json['start_date'] as String),
      endDate: json['end_date'] != null
          ? DateTime.parse(json['end_date'] as String)
          : null,
      type: AnomalyType.values.firstWhere(
        (t) => t.name == json['type'],
        orElse: () => AnomalyType.unknown,
      ),
      severity: AnomalySeverity.values.firstWhere(
        (s) => s.name == json['severity'],
        orElse: () => AnomalySeverity.medium,
      ),
      deviation: (json['deviation'] as num).toDouble(),
      explanation: json['explanation'] as String? ?? '',
    );
  }

  Map<String, dynamic> toJson() => {
        'id': id,
        'region_id': regionId,
        'start_date': startDate.toIso8601String(),
        'end_date': endDate?.toIso8601String(),
        'type': type.name,
        'severity': severity.name,
        'deviation': deviation,
        'explanation': explanation,
      };
}
