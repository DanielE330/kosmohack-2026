import 'package:flutter/material.dart';

import '../data/active_map_controller.dart';
import '../models/map_info.dart';
import '../theme.dart';
import 'share_map_dialog.dart';

/// Выпадающий список карт в сайдбаре — переключение между своими и
/// расшаренными картами, создание новой, доступ к диалогу "Поделиться"
/// для карты, которой владеет текущий пользователь.
class MapSwitcher extends StatelessWidget {
  const MapSwitcher({super.key, required this.controller});

  final ActiveMapController controller;

  Future<void> _openMenu(BuildContext context) async {
    final action = await showModalBottomSheet<_MenuAction>(
      context: context,
      showDragHandle: true,
      builder: (context) => _MapMenuSheet(controller: controller),
    );
    if (action == null || !context.mounted) return;
    switch (action) {
      case _MenuAction.create:
        await _promptCreate(context);
      case _MenuAction.share:
        final active = controller.active;
        if (active != null) {
          await showDialog(context: context, builder: (_) => ShareMapDialog(map: active, controller: controller));
        }
    }
  }

  Future<void> _promptCreate(BuildContext context) async {
    final textController = TextEditingController();
    final name = await showDialog<String>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Новая карта'),
        content: TextField(
          controller: textController,
          autofocus: true,
          decoration: const InputDecoration(hintText: 'Например, «Поля клиента N»'),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context), child: const Text('Отмена')),
          FilledButton(
            onPressed: () => Navigator.pop(context, textController.text.trim()),
            child: const Text('Создать'),
          ),
        ],
      ),
    );
    if (name != null && name.isNotEmpty) {
      await controller.create(name);
    }
  }

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: controller,
      builder: (context, _) {
        final active = controller.active;
        return InkWell(
          onTap: () => _openMenu(context),
          borderRadius: BorderRadius.circular(12),
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
            decoration: BoxDecoration(
              color: SkyTimeColors.cream,
              borderRadius: BorderRadius.circular(12),
            ),
            child: Row(
              children: [
                const Icon(Icons.map_outlined, size: 18, color: SkyTimeColors.navy),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    active?.name ?? (controller.loading ? 'Загрузка…' : 'Нет карт'),
                    style: const TextStyle(
                      fontSize: 12.5,
                      fontWeight: FontWeight.w700,
                      color: SkyTimeColors.navy,
                    ),
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
                const Icon(Icons.unfold_more, size: 16, color: SkyTimeColors.navy),
              ],
            ),
          ),
        );
      },
    );
  }
}

enum _MenuAction { create, share }

class _MapMenuSheet extends StatelessWidget {
  const _MapMenuSheet({required this.controller});

  final ActiveMapController controller;

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: controller,
      builder: (context, _) => SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 0, 16, 8),
              child: Text('Мои карты', style: Theme.of(context).textTheme.titleSmall),
            ),
            for (final map in controller.maps)
              ListTile(
                leading: Icon(
                  map.id == controller.active?.id ? Icons.radio_button_checked : Icons.radio_button_unchecked,
                  color: SkyTimeColors.teal,
                ),
                title: Text(map.name),
                subtitle: Text(_roleLabel(map.role)),
                onTap: () {
                  controller.select(map);
                  Navigator.pop(context);
                },
              ),
            ListTile(
              leading: const Icon(Icons.add),
              title: const Text('Новая карта'),
              onTap: () => Navigator.pop(context, _MenuAction.create),
            ),
            if (controller.active?.role == MapRole.owner)
              ListTile(
                leading: const Icon(Icons.share_outlined),
                title: const Text('Поделиться текущей картой'),
                onTap: () => Navigator.pop(context, _MenuAction.share),
              ),
            const SizedBox(height: 8),
          ],
        ),
      ),
    );
  }

  String _roleLabel(MapRole role) {
    switch (role) {
      case MapRole.owner:
        return 'Владелец';
      case MapRole.editor:
        return 'Можно редактировать';
      case MapRole.viewer:
        return 'Только просмотр';
    }
  }
}
