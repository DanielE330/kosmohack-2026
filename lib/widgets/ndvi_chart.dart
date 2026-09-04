import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

import '../models/ndvi_point.dart';

/// Line chart of actual NDVI against the climate-norm band (mean +/- std),
/// with anomalous points highlighted in red.
class NdviChart extends StatelessWidget {
  const NdviChart({super.key, required this.points});

  final List<NdviPoint> points;

  @override
  Widget build(BuildContext context) {
    if (points.isEmpty) {
      return const Center(child: Text('Нет данных за выбранный период'));
    }

    final actualSpots = <FlSpot>[];
    final normSpots = <FlSpot>[];
    final upperSpots = <FlSpot>[];
    final lowerSpots = <FlSpot>[];

    for (int i = 0; i < points.length; i++) {
      final p = points[i];
      actualSpots.add(FlSpot(i.toDouble(), p.ndvi));
      normSpots.add(FlSpot(i.toDouble(), p.normMean));
      upperSpots.add(FlSpot(i.toDouble(), p.normMean + p.normStd));
      lowerSpots.add(FlSpot(i.toDouble(), p.normMean - p.normStd));
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
              return LineTooltipItem(
                '${DateFormat('MMM yyyy').format(p.date)}\nNDVI ${p.ndvi.toStringAsFixed(2)}',
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
          // Actual NDVI, coloured red on anomalous points.
          LineChartBarData(
            spots: actualSpots,
            isCurved: true,
            color: const Color(0xFF2E7D32),
            barWidth: 3,
            dotData: FlDotData(
              show: true,
              getDotPainter: (spot, percent, bar, index) {
                final anomalous = points[index].isAnomalous;
                return FlDotCirclePainter(
                  radius: anomalous ? 4.5 : 2.5,
                  color: anomalous ? const Color(0xFFB3261E) : bar.color!,
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
