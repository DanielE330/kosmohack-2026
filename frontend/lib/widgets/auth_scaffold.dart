import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../theme.dart';
import 'skytime_logo.dart';

/// Общая «рамка» экранов входа и регистрации.
///
/// Раньше оба экрана были голой формой под стандартным AppBar и выглядели
/// как черновик рядом с тёмным hero главной. Здесь та же композиция, что
/// на главной: тёмная навигационная полоса с логотипом сверху, светлый
/// контент под ней, форма — карточкой по центру. Общая, чтобы вход и
/// регистрация не разъезжались при следующей правке одного из них.
class AuthScaffold extends StatelessWidget {
  const AuthScaffold({
    super.key,
    required this.title,
    required this.subtitle,
    required this.form,
    this.aside,
  });

  final String title;
  final String subtitle;

  /// Содержимое карточки с формой.
  final Widget form;

  /// Необязательный блок сбоку (на широких экранах) или под формой (на
  /// узких) — на входе это список демо-аккаунтов.
  final Widget? aside;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Scaffold(
      body: ListView(
        padding: EdgeInsets.zero,
        children: [
          const _AuthTopBar(),
          Padding(
            padding: const EdgeInsets.fromLTRB(20, 36, 20, 40),
            child: Center(
              child: ConstrainedBox(
                constraints: BoxConstraints(maxWidth: aside == null ? 460 : 900),
                child: LayoutBuilder(
                  builder: (context, constraints) {
                    final card = _FormCard(title: title, subtitle: subtitle, child: form);
                    final aside = this.aside;
                    if (aside == null) return card;
                    // Две колонки только когда каждой достаётся осмысленная
                    // ширина — иначе список аккаунтов уезжает под форму.
                    if (constraints.maxWidth >= 820) {
                      return Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Expanded(flex: 5, child: card),
                          const SizedBox(width: 28),
                          Expanded(flex: 4, child: aside),
                        ],
                      );
                    }
                    return Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [card, const SizedBox(height: 20), aside],
                    );
                  },
                ),
              ),
            ),
          ),
          Padding(
            padding: const EdgeInsets.only(bottom: 24),
            child: Center(
              child: Text(
                'SkyTime — мониторинг вегетационной динамики по данным ДЗЗ',
                textAlign: TextAlign.center,
                style: theme.textTheme.bodySmall,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _AuthTopBar extends StatelessWidget {
  const _AuthTopBar();

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      color: SkyTimeColors.navy,
      padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
      child: Row(
        children: [
          // Логотип ведёт на главную — привычнее, чем стрелка «назад»,
          // которая на прямом заходе по ссылке вела бы в никуда.
          MouseRegion(
            cursor: SystemMouseCursors.click,
            child: GestureDetector(
              onTap: () => context.go('/'),
              child: SkyTimeLogo(height: 22, color: SkyTimeColors.cream),
            ),
          ),
          const Spacer(),
          TextButton.icon(
            style: TextButton.styleFrom(foregroundColor: SkyTimeColors.cream),
            onPressed: () => context.go('/map'),
            icon: const Icon(Icons.map_outlined, size: 18),
            label: const Text('К карте'),
          ),
        ],
      ),
    );
  }
}

class _FormCard extends StatelessWidget {
  const _FormCard({required this.title, required this.subtitle, required this.child});

  final String title;
  final String subtitle;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Container(
      padding: const EdgeInsets.all(28),
      decoration: BoxDecoration(
        color: theme.cardColor,
        borderRadius: BorderRadius.circular(SkyTimeRadii.xlarge),
        border: Border.all(color: theme.colorScheme.outlineVariant),
        boxShadow: [
          BoxShadow(
            color: theme.shadowColor,
            blurRadius: 32,
            offset: const Offset(0, 12),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        mainAxisSize: MainAxisSize.min,
        children: [
          // Тонкая полоска бренд-градиента вместо иконки — тот же приём,
          // что на заголовке hero (teal → lime).
          Container(
            width: 44,
            height: 4,
            decoration: BoxDecoration(
              gradient: SkyTimeColors.accentGradient,
              borderRadius: BorderRadius.circular(SkyTimeRadii.pill),
            ),
          ),
          const SizedBox(height: 20),
          Text(title, style: theme.textTheme.headlineSmall),
          const SizedBox(height: 6),
          Text(subtitle, style: theme.textTheme.bodySmall),
          const SizedBox(height: 24),
          child,
        ],
      ),
    );
  }
}

/// Сообщение об ошибке формы — заметный блок, а не строчка красным
/// текстом: на прошлой версии её легко было не заметить под полями.
class AuthErrorBanner extends StatelessWidget {
  const AuthErrorBanner({super.key, required this.message});

  final String message;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
      decoration: BoxDecoration(
        color: scheme.error.withValues(alpha: 0.10),
        borderRadius: BorderRadius.circular(SkyTimeRadii.medium),
        border: Border.all(color: scheme.error.withValues(alpha: 0.35)),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(Icons.error_outline, size: 18, color: scheme.error),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              message,
              style: TextStyle(color: scheme.error, fontSize: 13, height: 1.4),
            ),
          ),
        ],
      ),
    );
  }
}
