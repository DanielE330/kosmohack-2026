import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

import '../models/ndvi_point.dart';
import '../utils/ndvi_style.dart';

/// Line chart of the plotted NDVI value (`value` — real observation, or the
/// gap-filled estimate where none exists) against the climate-norm band
/// (mean +/- std). Observed points are solid dots; gap-filled/restored
/// points are hollow rings, so the "исходный vs восстановленный ряд" the
/// spec asks for is visually explicit. Points are coloured by their
/// Z-score band (normal/suppression/critical).
class NdviChart extends StatelessWidget {
  const NdviChart({super.key, required this.points});

  final List<NdviPoint> points;

  @override
  Widget build(BuildContext context) {
    if (points.isEmpty) {
      return const Center(child: Text('Нет данных за выбранный период'));
    }

    final valueSpots = <FlSpot>[];
    final normSpots = <FlSpot>[];
    final upperSpots = <FlSpot>[];
    final lowerSpots = <FlSpot>[];

    for (int i = 0; i < points.length; i++) {
      final p = points[i];
      valueSpots.add(FlSpot(i.toDouble(), p.value));
      normSpots.add(FlSpot(i.toDouble(), p.climatologyMean));
      upperSpots.add(FlSpot(i.toDouble(), p.climatologyMean + p.climatologyStd));
      lowerSpots.add(FlSpot(i.toDouble(), p.climatologyMean - p.climatologyStd));
    }

    return LineChart(
      LineChartData(
        minY: 0,
        maxY: 1,
        gridData: const FlGridData(show: true, drawVerticalLine: false),
        titlesData: FlTitlesData(
          rightTitles:
              const AxisTitles(sideTitles: SideTitles(showTitles: false)),
          topTitles:
              const AxisTitles(sideTitles: SideTitles(showTitles: false)),
          leftTitles: AxisTitles(
            sideTitles: SideTitles(
              showTitles: true,
              reservedSize: 36,
              interval: 0.2,
              getTitlesWidget: (v, meta) => Text(v.toStringAsFixed(1),
                  style: const TextStyle(fontSize: 10)),
            ),
          ),
          bottomTitles: AxisTitles(
            sideTitles: SideTitles(
              showTitles: true,
              reservedSize: 28,
              interval: (points.length / 6).clamp(1, points.length).toDouble(),
              getTitlesWidget: (v, meta) {
                final idx = v.round();
                if (idx < 0 || idx >= points.length) return const SizedBox();
                return Padding(
                  padding: const EdgeInsets.only(top: 6),
                  child: Text(
                    DateFormat('MM.yy').format(points[idx].date),
                    style: const TextStyle(fontSize: 10),
                  ),
                );
              },
            ),
          ),
        ),
        borderData: FlBorderData(show: true),
        lineTouchData: LineTouchData(
          touchTooltipData: LineTouchTooltipData(
            getTooltipItems: (spots) => spots.map((s) {
              final idx = s.x.round();
              if (idx < 0 || idx >= points.length) return null;
              final p = points[idx];
              final kind = p.isRestored ? 'восстановлено' : 'наблюдение';
              return LineTooltipItem(
                '${DateFormat('MMM yyyy').format(p.date)}\n'
                'NDVI ${p.value.toStringAsFixed(2)} ($kind)\nZ ${p.zScore.toStringAsFixed(2)}',
                const TextStyle(color: Colors.white, fontSize: 11),
              );
            }).toList(),
          ),
        ),
        lineBarsData: [
          // Climate-norm band (upper/lower), filled between them.
          LineChartBarData(
            spots: upperSpots,
            isCurved: true,
            color: Colors.transparent,
            barWidth: 0,
            dotData: const FlDotData(show: false),
            belowBarData: BarAreaData(
              show: true,
              color: Colors.blueGrey.withValues(alpha: 0.15),
              cutOffY: 0,
              applyCutOffY: false,
            ),
          ),
          LineChartBarData(
            spots: lowerSpots,
            isCurved: true,
            color: Colors.transparent,
            barWidth: 0,
            dotData: const FlDotData(show: false),
          ),
          // Climate norm mean, dashed.
          LineChartBarData(
            spots: normSpots,
            isCurved: true,
            color: Colors.blueGrey,
            barWidth: 2,
            dashArray: [6, 4],
            dotData: const FlDotData(show: false),
          ),
          // Plotted NDVI value; solid dots = real observation, hollow
          // rings = gap-filled/restored, coloured by Z-score band.
          LineChartBarData(
            spots: valueSpots,
            isCurved: true,
            color: const Color(0xFF2E7D32),
            barWidth: 2,
            dotData: FlDotData(
              show: true,
              getDotPainter: (spot, percent, bar, index) {
                final p = points[index];
                final color = statusColor(p.status);
                if (p.isRestored) {
                  return FlDotCirclePainter(
                    radius: 3.5,
                    color: Colors.white,
                    strokeWidth: 2,
                    strokeColor: color,
                  );
                }
                return FlDotCirclePainter(
                  radius: p.status == NdviStatus.normal ? 2.5 : 4,
                  color: color,
                  strokeWidth: 0,
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}
