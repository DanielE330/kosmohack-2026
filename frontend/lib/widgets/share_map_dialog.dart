import 'package:flutter/material.dart';

import '../data/active_map_controller.dart';
import '../models/map_info.dart';

/// Приглашение по email на карту (viewer по умолчанию, можно editor) +
/// список текущих участников с возможностью убрать доступ. Только для
/// владельца карты — сайдбар (см. `map_switcher.dart`) уже не показывает
/// этот пункт меню для чужих/расшаренных карт, а бэкенд всё равно
/// перепроверяет права на каждый вызов.
class ShareMapDialog extends StatefulWidget {
  const ShareMapDialog({super.key, required this.map, required this.controller});

  final MapInfo map;
  final ActiveMapController controller;

  @override
  State<ShareMapDialog> createState() => _ShareMapDialogState();
}

class _ShareMapDialogState extends State<ShareMapDialog> {
  final _emailController = TextEditingController();
  MapRole _role = MapRole.viewer;
  List<MapMemberInfo> _members = [];
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() => _loading = true);
    try {
      final members = await widget.controller.service.getMapMembers(widget.map.id);
      if (!mounted) return;
      setState(() {
        _members = members;
        _loading = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _error = 'Не удалось загрузить участников: $e';
        _loading = false;
      });
    }
  }

  Future<void> _invite() async {
    final email = _emailController.text.trim();
    if (email.isEmpty) return;
    try {
      await widget.controller.service.inviteToMap(widget.map.id, email: email, role: _role);
      _emailController.clear();
      await _load();
    } catch (e) {
      if (!mounted) return;
      setState(() => _error = e.toString().replaceFirst('Exception: ', ''));
    }
  }

  Future<void> _remove(MapMemberInfo member) async {
    try {
      await widget.controller.service.removeMapMember(widget.map.id, member.userId);
      await _load();
    } catch (e) {
      if (!mounted) return;
      setState(() => _error = e.toString().replaceFirst('Exception: ', ''));
    }
  }

  @override
  void dispose() {
    _emailController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: Text('Поделиться картой «${widget.map.name}»'),
      content: SizedBox(
        width: 380,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: _emailController,
                    decoration: const InputDecoration(hintText: 'email коллеги'),
                    keyboardType: TextInputType.emailAddress,
                  ),
                ),
                const SizedBox(width: 8),
                DropdownButton<MapRole>(
                  value: _role,
                  items: const [
                    DropdownMenuItem(value: MapRole.viewer, child: Text('Просмотр')),
                    DropdownMenuItem(value: MapRole.editor, child: Text('Редактирование')),
                  ],
                  onChanged: (role) => setState(() => _role = role ?? MapRole.viewer),
                ),
              ],
            ),
            const SizedBox(height: 8),
            Align(
              alignment: Alignment.centerRight,
              child: FilledButton(onPressed: _invite, child: const Text('Пригласить')),
            ),
            if (_error != null) ...[
              const SizedBox(height: 8),
              Text(_error!, style: TextStyle(color: Theme.of(context).colorScheme.error, fontSize: 12.5)),
            ],
            const Divider(height: 24),
            if (_loading)
              const Center(child: CircularProgressIndicator())
            else if (_members.isEmpty)
              const Text('Пока никого не пригласили.')
            else
              for (final member in _members)
                ListTile(
                  contentPadding: EdgeInsets.zero,
                  title: Text(member.invitedEmail),
                  subtitle: Text(member.role == MapRole.editor ? 'Редактирование' : 'Просмотр'),
                  trailing: IconButton(
                    icon: const Icon(Icons.close),
                    tooltip: 'Убрать доступ',
                    onPressed: () => _remove(member),
                  ),
                ),
          ],
        ),
      ),
      actions: [
        TextButton(onPressed: () => Navigator.pop(context), child: const Text('Готово')),
      ],
    );
  }
}
