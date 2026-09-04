import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

/// Слайдер, задающий дату «на момент» для всей карты: выбирает индекс в
/// загруженных датах временного ряда NDVI.
class TimeSlider extends StatelessWidget {
  const TimeSlider({
    super.key,
    required this.dates,
    required this.index,
    required this.onChanged,
  });

  final List<DateTime> dates;
  final int index;
  final ValueChanged<int> onChanged;

  @override
  Widget build(BuildContext context) {
    if (dates.isEmpty) return const SizedBox.shrink();
    final safeIndex = index.clamp(0, dates.length - 1);
    final label = DateFormat('MMMM yyyy', 'ru').format(dates[safeIndex]);

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surface,
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.08),
            blurRadius: 8,
            offset: const Offset(0, -2),
          ),
        ],
      ),
      child: Row(
        children: [
          IconButton(
            icon: const Icon(Icons.chevron_left),
            onPressed: safeIndex > 0 ? () => onChanged(safeIndex - 1) : null,
            tooltip: 'Предыдущий месяц',
          ),
          Expanded(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(label, style: Theme.of(context).textTheme.labelLarge),
                Slider(
                  value: safeIndex.toDouble(),
                  min: 0,
                  max: (dates.length - 1).toDouble(),
                  divisions: dates.length > 1 ? dates.length - 1 : null,
                  label: label,
                  onChanged: (v) => onChanged(v.round()),
                ),
              ],
            ),
          ),
          IconButton(
            icon: const Icon(Icons.chevron_right),
            onPressed: safeIndex < dates.length - 1
                ? () => onChanged(safeIndex + 1)
                : null,
            tooltip: 'Следующий месяц',
          ),
        ],
      ),
    );
  }
}
