import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../data/active_map_controller.dart';
import '../data/status_transition_tracker.dart';
import '../theme.dart';
import 'map_switcher.dart';
import 'skytime_logo.dart';

/// Раздел навигации в левом сайдбаре — по референсу макета из `style/`
/// (`SkyTime Map & Account.dc.html`).
enum DashboardSection { map, account, analytics, notifications, reports, settings }

/// Обёртка с постоянным левым сайдбаром на широких экранах (desktop-style
/// дашборд) — на узких (телефон/планшет) просто отдаёт [child] как есть,
/// без сайдбара: там навигация остаётся через AppBar, как и была.
class DashboardShell extends StatelessWidget {
  const DashboardShell({super.key, required this.active, required this.child, this.activeMapController});

  final DashboardSection active;
  final Widget child;
  /// `null` — переключатель карт не показывается (напр. на экранах, где
  /// он не нужен); не обязателен для существующих мест использования.
  final ActiveMapController? activeMapController;

  static const _wideBreakpoint = 900.0;

  @override
  Widget build(BuildContext context) {
    final isWide = MediaQuery.sizeOf(context).width >= _wideBreakpoint;
    if (!isWide) return child;

    // Отдельный внешний Scaffold — чтобы у сайдбара был свой
    // ScaffoldMessenger для снэкбара "скоро" (сам [child] — это уже
    // самостоятельный Scaffold со своим AppBar, вложенность допустима).
    return Scaffold(
      body: Row(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          _Sidebar(active: active, activeMapController: activeMapController),
          Expanded(child: child),
        ],
      ),
    );
  }
}

class _Sidebar extends StatefulWidget {
  const _Sidebar({required this.active, this.activeMapController});

  final DashboardSection active;
  final ActiveMapController? activeMapController;

  @override
  State<_Sidebar> createState() => _SidebarState();
}

class _SidebarState extends State<_Sidebar> {
  @override
  void initState() {
    super.initState();
    // Сайдбар пересоздаётся при переходе на любой экран (DashboardShell
    // оборачивает их все) — удобное место обновлять счётчик уведомлений,
    // не заставляя каждый экран явно об этом заботиться.
    final controller = widget.activeMapController;
    if (controller != null) {
      StatusTransitionTracker.instance.refresh(controller);
    }
  }

  static const _items = [
    (DashboardSection.map, Icons.grid_view_outlined, 'Карта'),
    (DashboardSection.account, Icons.list_alt_outlined, 'Участки'),
    (DashboardSection.analytics, Icons.bar_chart_outlined, 'Аналитика'),
    (DashboardSection.notifications, Icons.notifications_outlined, 'Уведомления'),
    (DashboardSection.reports, Icons.description_outlined, 'Отчёты'),
    (DashboardSection.settings, Icons.settings_outlined, 'Настройки'),
  ];

  void _onTap(BuildContext context, DashboardSection section) {
    switch (section) {
      case DashboardSection.map:
        context.go('/map');
      case DashboardSection.account:
        context.go('/account');
      case DashboardSection.analytics:
        context.go('/analytics');
      case DashboardSection.notifications:
        context.go('/notifications');
      case DashboardSection.reports:
        context.go('/reports');
      case DashboardSection.settings:
        context.go('/settings');
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Container(
      width: 216,
      padding: const EdgeInsets.symmetric(vertical: 20, horizontal: 14),
      decoration: BoxDecoration(
        // Из темы, а не хардкодом в белый: в тёмной теме белый сайдбар
        // рядом с тёмным контентом выглядел как непрокрашенный блок.
        color: theme.cardColor,
        border: Border(right: BorderSide(color: theme.dividerColor)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          // Логотип — точка возврата на главную, как в шапке остальных
          // экранов; заодно сайдбар перестаёт начинаться «с воздуха».
          Padding(
            padding: const EdgeInsets.only(left: 6, bottom: 18),
            child: Align(
              alignment: Alignment.centerLeft,
              child: MouseRegion(
                cursor: SystemMouseCursors.click,
                child: GestureDetector(
                  onTap: () => context.go('/'),
                  child: SkyTimeLogo(
                    height: 20,
                    color: theme.colorScheme.onSurface,
                  ),
                ),
              ),
            ),
          ),
          if (widget.activeMapController != null) ...[
            MapSwitcher(controller: widget.activeMapController!),
            const SizedBox(height: 16),
          ],
          for (final (section, icon, label) in _items) ...[
            section == DashboardSection.notifications
                ? ValueListenableBuilder<int>(
                    valueListenable: StatusTransitionTracker.instance.unseenCount,
                    builder: (context, count, _) => _SidebarItem(
                      icon: icon,
                      label: label,
                      selected: section == widget.active,
                      badgeCount: count,
                      onTap: () => _onTap(context, section),
                    ),
                  )
                : _SidebarItem(
                    icon: icon,
                    label: label,
                    selected: section == widget.active,
                    onTap: () => _onTap(context, section),
                  ),
            const SizedBox(height: 4),
          ],
          const Spacer(),
          const _InfoCard(
            icon: Icons.satellite_alt_outlined,
            title: 'Sentinel-2',
            subtitle: '10 м/пиксель',
          ),
        ],
      ),
    );
  }
}

class _SidebarItem extends StatelessWidget {
  const _SidebarItem({
    required this.icon,
    required this.label,
    required this.selected,
    required this.onTap,
    this.badgeCount = 0,
  });

  final IconData icon;
  final String label;
  final bool selected;
  final VoidCallback onTap;
  /// >0 — непросмотренные уведомления (переходы штатно↔не штатно с
  /// последнего визита на /notifications), см. `status_transition_tracker.dart`.
  final int badgeCount;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    // Невыбранный пункт — приглушённый цвет текста темы (в тёмной теме
    // navy на тёмном фоне был нечитаем).
    final idleColor = scheme.onSurface.withValues(alpha: 0.72);
    return Material(
      color: selected ? SkyTimeColors.teal : Colors.transparent,
      borderRadius: BorderRadius.circular(SkyTimeRadii.medium),
      child: InkWell(
        borderRadius: BorderRadius.circular(SkyTimeRadii.medium),
        // Наведение подсвечивает пункт тем же акцентом, что и выбор, —
        // видно, что строка кликабельна, ещё до клика.
        hoverColor: SkyTimeColors.teal.withValues(alpha: selected ? 0.0 : 0.10),
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 11),
          child: Row(
            children: [
              Icon(
                icon,
                size: 18,
                color: selected ? Colors.white : idleColor,
              ),
              const SizedBox(width: 10),
              Expanded(
                child: Text(
                  label,
                  style: TextStyle(
                    fontSize: 13,
                    fontWeight: FontWeight.w700,
                    color: selected ? Colors.white : idleColor,
                  ),
                ),
              ),
              if (badgeCount > 0)
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                  decoration: BoxDecoration(
                    color: selected ? Colors.white : const Color(0xFFB3261E),
                    borderRadius: BorderRadius.circular(999),
                  ),
                  child: Text(
                    '$badgeCount',
                    style: TextStyle(
                      fontSize: 10.5,
                      fontWeight: FontWeight.w800,
                      color: selected ? SkyTimeColors.teal : Colors.white,
                    ),
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }
}

class _InfoCard extends StatelessWidget {
  const _InfoCard({required this.icon, required this.title, required this.subtitle});

  final IconData icon;
  final String title;
  final String subtitle;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
      decoration: BoxDecoration(
        color: scheme.surfaceContainerHigh,
        borderRadius: BorderRadius.circular(SkyTimeRadii.medium),
        border: Border.all(color: scheme.outlineVariant),
      ),
      child: Row(
        children: [
          Icon(icon, size: 18, color: SkyTimeColors.teal),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(title,
                    style: TextStyle(
                        fontSize: 11, fontWeight: FontWeight.w800, color: scheme.onSurface)),
                Text(subtitle,
                    style: TextStyle(
                        fontSize: 10.5, color: scheme.onSurface.withValues(alpha: 0.7))),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
