import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../data/active_map_controller.dart';
import '../data/auth_repository.dart';
import '../theme.dart';
import '../theme_controller.dart';
import '../widgets/dashboard_shell.dart';

class SettingsScreen extends StatelessWidget {
  const SettingsScreen({
    super.key,
    required this.auth,
    required this.themeController,
    required this.activeMapController,
  });

  final AuthRepository auth;
  final ThemeController themeController;
  final ActiveMapController activeMapController;

  @override
  Widget build(BuildContext context) {
    return DashboardShell(
      active: DashboardSection.settings,
      activeMapController: activeMapController,
      child: Scaffold(
        appBar: AppBar(
          leading: IconButton(
            icon: const Icon(Icons.arrow_back),
            onPressed: () => context.go('/map'),
          ),
          title: const Text('Настройки'),
        ),
        body: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            // Раньше жило в "Участках" — перенесено сюда: карточка входа
            // логичнее среди прочих настроек аккаунта, а "Участки" остаётся
            // чисто про список полигонов.
            AnimatedBuilder(
              animation: auth,
              builder: (context, _) {
                final loggedIn = auth.isLoggedIn;
                return Card(
                  child: ListTile(
                    leading: CircleAvatar(
                      backgroundColor: SkyTimeColors.teal,
                      child: Icon(
                        loggedIn ? Icons.person : Icons.person_outline,
                        color: Colors.white,
                      ),
                    ),
                    title: Text(loggedIn ? (auth.email ?? '') : 'Вы не вошли'),
                    subtitle: Text(
                      loggedIn
                          ? 'Аккаунт подтверждён'
                          : 'Войдите, чтобы сохранять свои полигоны на сервере',
                    ),
                    trailing: loggedIn
                        ? TextButton(onPressed: auth.logout, child: const Text('Выйти'))
                        : TextButton(
                            onPressed: () => context.go('/login'),
                            child: const Text('Войти'),
                          ),
                  ),
                );
              },
            ),
            const SizedBox(height: 24),
            Text('Оформление', style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 8),
            Card(
              child: ListenableBuilder(
                listenable: themeController,
                builder: (context, _) => SwitchListTile(
                  title: const Text('Тёмная тема'),
                  subtitle: const Text('Хранится только в этой вкладке — сбрасывается при перезагрузке'),
                  value: themeController.isDark,
                  onChanged: (_) => themeController.toggle(),
                ),
              ),
            ),
            const SizedBox(height: 24),
            Text('Аккаунт', style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 8),
            AnimatedBuilder(
              animation: auth,
              builder: (context, _) {
                if (!auth.isLoggedIn) {
                  return Card(
                    child: Padding(
                      padding: const EdgeInsets.all(16),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Text('Смена почты и пароля доступна только вошедшим пользователям.'),
                          const SizedBox(height: 12),
                          FilledButton(
                            onPressed: () => context.go('/login'),
                            child: const Text('Войти'),
                          ),
                        ],
                      ),
                    ),
                  );
                }
                return Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    _ChangeEmailCard(auth: auth),
                    const SizedBox(height: 16),
                    _ChangePasswordCard(auth: auth),
                  ],
                );
              },
            ),
          ],
        ),
      ),
    );
  }
}

class _ChangeEmailCard extends StatefulWidget {
  const _ChangeEmailCard({required this.auth});
  final AuthRepository auth;

  @override
  State<_ChangeEmailCard> createState() => _ChangeEmailCardState();
}

class _ChangeEmailCardState extends State<_ChangeEmailCard> {
  final _newEmailController = TextEditingController();
  final _passwordController = TextEditingController();
  bool _loading = false;
  String? _error;

  @override
  void dispose() {
    _newEmailController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    final newEmail = _newEmailController.text.trim();
    final password = _passwordController.text;
    if (newEmail.isEmpty || password.isEmpty) {
      setState(() => _error = 'Заполните оба поля');
      return;
    }
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final result = await widget.auth.changeEmail(newEmail: newEmail, password: password);
      if (!mounted) return;
      final uri = Uri(
        path: '/confirm-email',
        queryParameters: {'token': result.confirmationToken, 'email': result.email},
      );
      context.go(uri.toString());
    } catch (e) {
      if (!mounted) return;
      setState(() => _error = e.toString().replaceFirst('Exception: ', ''));
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text('Сменить почту', style: Theme.of(context).textTheme.titleSmall),
            const SizedBox(height: 4),
            Text('Текущая: ${widget.auth.email ?? ''}', style: TextStyle(color: Theme.of(context).hintColor, fontSize: 12.5)),
            const SizedBox(height: 12),
            TextField(
              controller: _newEmailController,
              decoration: const InputDecoration(labelText: 'Новая почта'),
              keyboardType: TextInputType.emailAddress,
            ),
            const SizedBox(height: 8),
            TextField(
              controller: _passwordController,
              decoration: const InputDecoration(labelText: 'Текущий пароль (подтверждение)'),
              obscureText: true,
            ),
            if (_error != null) ...[
              const SizedBox(height: 8),
              Text(_error!, style: TextStyle(color: Theme.of(context).colorScheme.error, fontSize: 12.5)),
            ],
            const SizedBox(height: 12),
            FilledButton(
              onPressed: _loading ? null : _submit,
              child: _loading
                  ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2))
                  : const Text('Сменить почту'),
            ),
          ],
        ),
      ),
    );
  }
}

class _ChangePasswordCard extends StatefulWidget {
  const _ChangePasswordCard({required this.auth});
  final AuthRepository auth;

  @override
  State<_ChangePasswordCard> createState() => _ChangePasswordCardState();
}

class _ChangePasswordCardState extends State<_ChangePasswordCard> {
  final _oldController = TextEditingController();
  final _newController = TextEditingController();
  final _confirmController = TextEditingController();
  final _tokenController = TextEditingController();
  bool _loading = false;
  String? _error;
  bool _success = false;
  // Не null — пароль запрошен, ждём подтверждения токеном (см.
  // POST /auth/change-password — вступает в силу только после
  // /auth/confirm-password-change, как и смена почты).
  bool _awaitingConfirmation = false;

  @override
  void dispose() {
    _oldController.dispose();
    _newController.dispose();
    _confirmController.dispose();
    _tokenController.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    final oldPassword = _oldController.text;
    final newPassword = _newController.text;
    final confirm = _confirmController.text;
    if (oldPassword.isEmpty || newPassword.isEmpty) {
      setState(() {
        _error = 'Заполните все поля';
        _success = false;
      });
      return;
    }
    if (newPassword.length < 8) {
      setState(() {
        _error = 'Новый пароль должен быть не короче 8 символов';
        _success = false;
      });
      return;
    }
    if (newPassword != confirm) {
      setState(() {
        _error = 'Пароли не совпадают';
        _success = false;
      });
      return;
    }
    setState(() {
      _loading = true;
      _error = null;
      _success = false;
    });
    try {
      // Токен подставлен сразу в поле — та же подстраховка, что и на
      // экране подтверждения почты, на случай если письмо не дойдёт.
      final token = await widget.auth.changePassword(oldPassword: oldPassword, newPassword: newPassword);
      if (!mounted) return;
      _tokenController.text = token;
      setState(() => _awaitingConfirmation = true);
    } catch (e) {
      if (!mounted) return;
      setState(() => _error = e.toString().replaceFirst('Exception: ', ''));
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _confirm() async {
    final token = _tokenController.text.trim();
    if (token.isEmpty) {
      setState(() => _error = 'Введите токен подтверждения');
      return;
    }
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      await widget.auth.confirmPasswordChange(token);
      if (!mounted) return;
      _oldController.clear();
      _newController.clear();
      _confirmController.clear();
      _tokenController.clear();
      setState(() {
        _awaitingConfirmation = false;
        _success = true;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() => _error = e.toString().replaceFirst('Exception: ', ''));
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text('Сменить пароль', style: Theme.of(context).textTheme.titleSmall),
            const SizedBox(height: 12),
            if (_awaitingConfirmation) ...[
              const Text(
                'Токен подтверждения также должен прийти письмом — но на '
                'случай, если почта задержится, он уже подставлен в поле '
                'ниже: просто нажмите «Подтвердить».',
                style: TextStyle(fontSize: 12.5),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: _tokenController,
                decoration: const InputDecoration(labelText: 'Токен подтверждения'),
              ),
              if (_error != null) ...[
                const SizedBox(height: 8),
                Text(_error!, style: TextStyle(color: Theme.of(context).colorScheme.error, fontSize: 12.5)),
              ],
              const SizedBox(height: 12),
              FilledButton(
                onPressed: _loading ? null : _confirm,
                child: _loading
                    ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2))
                    : const Text('Подтвердить'),
              ),
            ] else ...[
              TextField(
                controller: _oldController,
                decoration: const InputDecoration(labelText: 'Текущий пароль'),
                obscureText: true,
              ),
              const SizedBox(height: 8),
              TextField(
                controller: _newController,
                decoration: const InputDecoration(labelText: 'Новый пароль'),
                obscureText: true,
              ),
              const SizedBox(height: 8),
              TextField(
                controller: _confirmController,
                decoration: const InputDecoration(labelText: 'Повторите новый пароль'),
                obscureText: true,
              ),
              if (_error != null) ...[
                const SizedBox(height: 8),
                Text(_error!, style: TextStyle(color: Theme.of(context).colorScheme.error, fontSize: 12.5)),
              ],
              if (_success) ...[
                const SizedBox(height: 8),
                const Text('Пароль обновлён.', style: TextStyle(color: Color(0xFF2E7D32), fontSize: 12.5)),
              ],
              const SizedBox(height: 12),
              FilledButton(
                onPressed: _loading ? null : _submit,
                child: _loading
                    ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2))
                    : const Text('Сменить пароль'),
              ),
            ],
          ],
        ),
      ),
    );
  }
}
