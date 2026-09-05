import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../theme.dart';

/// Раздел навигации в левом сайдбаре — по референсу макета из `style/`
/// (`SkyTime Map & Account.dc.html`).
enum DashboardSection { map, account, analytics, notifications, reports, settings }

/// Обёртка с постоянным левым сайдбаром на широких экранах (desktop-style
/// дашборд) — на узких (телефон/планшет) просто отдаёт [child] как есть,
/// без сайдбара: там навигация остаётся через AppBar, как и была.
class DashboardShell extends StatelessWidget {
  const DashboardShell({super.key, required this.active, required this.child});

  final DashboardSection active;
  final Widget child;

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
          _Sidebar(active: active),
          Expanded(child: child),
        ],
      ),
    );
  }
}

class _Sidebar extends StatelessWidget {
  const _Sidebar({required this.active});

  final DashboardSection active;

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
    return Container(
      width: 216,
      padding: const EdgeInsets.symmetric(vertical: 20, horizontal: 14),
      decoration: BoxDecoration(
        color: Colors.white,
        border: Border(right: BorderSide(color: Theme.of(context).dividerColor)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          for (final (section, icon, label) in _items) ...[
            _SidebarItem(
              icon: icon,
              label: label,
              selected: section == active,
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
  });

  final IconData icon;
  final String label;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: selected ? SkyTimeColors.teal : Colors.transparent,
      borderRadius: BorderRadius.circular(12),
      child: InkWell(
        borderRadius: BorderRadius.circular(12),
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 11),
          child: Row(
            children: [
              Icon(
                icon,
                size: 18,
                color: selected ? Colors.white : SkyTimeColors.navy.withValues(alpha: 0.72),
              ),
              const SizedBox(width: 10),
              Text(
                label,
                style: TextStyle(
                  fontSize: 13,
                  fontWeight: FontWeight.w700,
                  color: selected ? Colors.white : SkyTimeColors.navy.withValues(alpha: 0.72),
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
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
      decoration: BoxDecoration(
        color: SkyTimeColors.cream,
        borderRadius: BorderRadius.circular(14),
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
                    style: const TextStyle(
                        fontSize: 11, fontWeight: FontWeight.w800, color: SkyTimeColors.navy)),
                Text(subtitle,
                    style: TextStyle(
                        fontSize: 10.5, color: SkyTimeColors.navy.withValues(alpha: 0.7))),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
