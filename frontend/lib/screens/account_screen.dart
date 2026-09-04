import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../data/auth_repository.dart';
import '../data/vegetation_data_service.dart';
import '../models/ndvi_polygon.dart';
import '../theme.dart';

/// Личный кабинет: кто вошёл, свои полигоны, быстрые действия
/// («создать полигон», «посмотреть все на карте»). «Свои» полигоны —
/// это `isCustom == true`: в моке они все принадлежат текущей сессии,
/// на реальном бэкенде — те, что создал текущий пользователь (владелец
/// проверяется на сервере при изменении/удалении).
class AccountScreen extends StatefulWidget {
  const AccountScreen({super.key, required this.service, required this.auth});

  final VegetationDataService service;
  final AuthRepository auth;

  @override
  State<AccountScreen> createState() => _AccountScreenState();
}

class _AccountScreenState extends State<AccountScreen> {
  List<NdviPolygon> _myPolygons = [];
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    widget.auth.addListener(_onAuthChanged);
    _load();
  }

  @override
  void dispose() {
    widget.auth.removeListener(_onAuthChanged);
    super.dispose();
  }

  void _onAuthChanged() => setState(() {});

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final all = await widget.service.getPolygons();
      setState(() {
        _myPolygons = all.where((p) => p.isCustom).toList();
        _loading = false;
      });
    } catch (e) {
      setState(() {
        _error = 'Не удалось загрузить полигоны: $e';
        _loading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final loggedIn = widget.auth.isLoggedIn;
    return Scaffold(
      appBar: AppBar(
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          onPressed: () => context.go('/'),
        ),
        title: const Text('Личный кабинет'),
      ),
      body: RefreshIndicator(
        onRefresh: _load,
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            Card(
              child: ListTile(
                leading: CircleAvatar(
                  backgroundColor: SkyTimeColors.teal,
                  child: Icon(
                    loggedIn ? Icons.person : Icons.person_outline,
                    color: Colors.white,
                  ),
                ),
                title: Text(loggedIn ? (widget.auth.email ?? '') : 'Вы не вошли'),
                subtitle: Text(
                  loggedIn
                      ? 'Аккаунт подтверждён'
                      : 'Войдите, чтобы сохранять свои полигоны на сервере',
                ),
                trailing: loggedIn
                    ? TextButton(onPressed: widget.auth.logout, child: const Text('Выйти'))
                    : TextButton(
                        onPressed: () => context.push('/login'),
                        child: const Text('Войти'),
                      ),
              ),
            ),
            const SizedBox(height: 16),
            Wrap(
              spacing: 12,
              runSpacing: 12,
              children: [
                FilledButton.icon(
                  onPressed: () {
                    if (!widget.auth.isLoggedIn) {
                      context.push('/login');
                      return;
                    }
                    context.go('/?draw=1');
                  },
                  icon: const Icon(Icons.add_location_alt_outlined),
                  label: const Text('Создать полигон'),
                ),
                OutlinedButton.icon(
                  onPressed: () => context.go('/'),
                  icon: const Icon(Icons.map_outlined),
                  label: const Text('Посмотреть все на карте'),
                ),
              ],
            ),
            const SizedBox(height: 24),
            Text('Мои полигоны', style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 8),
            if (_loading)
              const Padding(
                padding: EdgeInsets.all(24),
                child: Center(child: CircularProgressIndicator()),
              )
            else if (_error != null)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 12),
                child: Text(_error!),
              )
            else if (_myPolygons.isEmpty)
              const Padding(
                padding: EdgeInsets.symmetric(vertical: 12),
                child: Text('Пока нет своих полигонов — нарисуйте первый на карте.'),
              )
            else
              ..._myPolygons.map(
                (p) => Card(
                  margin: const EdgeInsets.only(bottom: 8),
                  child: ListTile(
                    leading: const Icon(Icons.crop_square, color: SkyTimeColors.teal),
                    title: Text(p.label),
                    subtitle: Text('${p.id} · ${p.cropType}'),
                    trailing: const Icon(Icons.chevron_right),
                    onTap: () => context.push('/polygon/${p.id}'),
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }
}
