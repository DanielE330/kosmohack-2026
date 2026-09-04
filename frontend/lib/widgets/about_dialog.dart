import 'package:flutter/material.dart';

/// Краткое описание проекта — раньше было отдельной страницей-лендингом
/// на "/", из-за которой до демо-карты нужно было ещё кликать «Попробовать
/// демо». Теперь карта открывается сразу на "/", а это описание доступно
/// по кнопке «О проекте» в AppBar, не блокируя доступ к демо.
Future<void> showSkyTimeAboutDialog(BuildContext context) {
  return showDialog(
    context: context,
    builder: (context) => AlertDialog(
      title: Row(
        children: [
          const Icon(Icons.satellite_alt, color: Color(0xFF2E7D32)),
          const SizedBox(width: 8),
          const Text('SkyTime'),
        ],
      ),
      content: SizedBox(
        width: 420,
        child: SingleChildScrollView(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisSize: MainAxisSize.min,
            children: [
              const Text(
                'Мониторинг вегетационной динамики сельхозполей по '
                'спутниковым данным NDVI — восстановление пропусков и '
                'детекция аномалий.',
              ),
              const SizedBox(height: 16),
              const _FeatureRow(
                icon: Icons.map_outlined,
                title: 'Карта полей',
                text: 'Выберите готовый контур поля или нарисуйте свой прямо на карте.',
              ),
              const _FeatureRow(
                icon: Icons.show_chart,
                title: 'Временной ряд NDVI',
                text: 'График показывает и реальные наблюдения, и восстановленные '
                    'значения там, где данных не было — отдельно.',
              ),
              const _FeatureRow(
                icon: Icons.warning_amber_rounded,
                title: 'Аномалии по Z-score',
                text: 'Штатное развитие / угнетение биомассы / критическая аномалия — '
                    'с объяснением вероятной причины.',
              ),
              const _FeatureRow(
                icon: Icons.travel_explore,
                title: 'Работа с любым регионом',
                text: 'Автопоиск контуров в новой области, управление своим набором '
                    'полей: добавить, отредактировать, удалить.',
              ),
              const SizedBox(height: 8),
              Text(
                'Карта работает на тестовых данных без регистрации. Аккаунт нужен '
                'только для сохранения своих полигонов на реальном сервере.',
                style: Theme.of(context).textTheme.bodySmall,
              ),
            ],
          ),
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(),
          child: const Text('Закрыть'),
        ),
      ],
    ),
  );
}

class _FeatureRow extends StatelessWidget {
  const _FeatureRow({required this.icon, required this.title, required this.text});

  final IconData icon;
  final String title;
  final String text;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, size: 20, color: const Color(0xFF2E7D32)),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(title, style: Theme.of(context).textTheme.titleSmall),
                Text(text, style: Theme.of(context).textTheme.bodySmall),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
