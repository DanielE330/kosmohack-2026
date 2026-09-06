import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../data/auth_repository.dart';
import '../data/demo_accounts.dart';
import '../theme.dart';
import '../widgets/auth_scaffold.dart';

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key, required this.auth});

  final AuthRepository auth;

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _formKey = GlobalKey<FormState>();
  final _emailController = TextEditingController();
  final _passwordController = TextEditingController();
  bool _loading = false;
  bool _obscurePassword = true;
  String? _error;

  @override
  void dispose() {
    _emailController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      await widget.auth.login(
        email: _emailController.text.trim(),
        password: _passwordController.text,
      );
      if (!mounted) return;
      context.go('/map');
    } catch (e) {
      if (!mounted) return;
      setState(() => _error = e.toString().replaceFirst('Exception: ', ''));
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  void _fill(DemoAccount account) {
    setState(() {
      _emailController.text = account.email;
      _passwordController.text = account.password;
      // Подставленный пароль полезно показать: это витринные данные, и
      // пользователю нужно видеть, что именно попало в поле.
      _obscurePassword = false;
      _error = null;
    });
  }

  @override
  Widget build(BuildContext context) {
    return AuthScaffold(
      title: 'Вход в SkyTime',
      subtitle: 'Свои участки, история NDVI и уведомления об аномалиях',
      aside: _DemoAccountsPanel(onPick: _fill),
      form: Form(
        key: _formKey,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          mainAxisSize: MainAxisSize.min,
          children: [
            TextFormField(
              controller: _emailController,
              keyboardType: TextInputType.emailAddress,
              autofillHints: const [AutofillHints.email],
              decoration: const InputDecoration(
                labelText: 'Email',
                prefixIcon: Icon(Icons.alternate_email, size: 20),
              ),
              validator: (v) => (v == null || !v.contains('@')) ? 'Введите email' : null,
            ),
            const SizedBox(height: 14),
            TextFormField(
              controller: _passwordController,
              obscureText: _obscurePassword,
              autofillHints: const [AutofillHints.password],
              decoration: InputDecoration(
                labelText: 'Пароль',
                prefixIcon: const Icon(Icons.lock_outline, size: 20),
                suffixIcon: IconButton(
                  tooltip: _obscurePassword ? 'Показать пароль' : 'Скрыть пароль',
                  icon: Icon(
                    _obscurePassword ? Icons.visibility_outlined : Icons.visibility_off_outlined,
                    size: 20,
                  ),
                  onPressed: () => setState(() => _obscurePassword = !_obscurePassword),
                ),
              ),
              validator: (v) => (v == null || v.isEmpty) ? 'Введите пароль' : null,
              onFieldSubmitted: (_) => _submit(),
            ),
            if (_error != null) ...[
              const SizedBox(height: 16),
              AuthErrorBanner(message: _error!),
            ],
            const SizedBox(height: 22),
            FilledButton(
              onPressed: _loading ? null : _submit,
              child: _loading
                  ? const SizedBox(
                      width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2))
                  : const Text('Войти'),
            ),
            const SizedBox(height: 8),
            TextButton(
              onPressed: () => context.go('/register'),
              child: const Text('Нет аккаунта? Зарегистрироваться'),
            ),
          ],
        ),
      ),
    );
  }
}

/// Список демо-аккаунтов с подстановкой в поля.
///
/// Показывается всегда, не только на моке: на реальном бэкенде это
/// настоящие пользователи, которых заводит сид при старте
/// (`backend/app/services/demo_seed.py`). Раньше здесь была одна строчка
/// про `demo@skytime.dev` — теперь видно и то, что аккаунтов несколько, и
/// чем они отличаются по правам на общей карте.
class _DemoAccountsPanel extends StatelessWidget {
  const _DemoAccountsPanel({required this.onPick});

  final void Function(DemoAccount account) onPick;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: theme.colorScheme.surfaceContainerHigh,
        borderRadius: BorderRadius.circular(SkyTimeRadii.xlarge),
        border: Border.all(color: theme.colorScheme.outlineVariant),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        mainAxisSize: MainAxisSize.min,
        children: [
          Row(
            children: [
              const Icon(Icons.badge_outlined, size: 18, color: SkyTimeColors.teal),
              const SizedBox(width: 8),
              Expanded(
                child: Text('Демо-доступ', style: theme.textTheme.titleMedium),
              ),
            ],
          ),
          const SizedBox(height: 6),
          Text(
            'Готовые аккаунты для показа. Нажмите на карточку — логин и '
            'пароль подставятся в форму.',
            style: theme.textTheme.bodySmall,
          ),
          const SizedBox(height: 14),
          for (final account in demoAccounts) ...[
            _DemoAccountTile(account: account, onTap: () => onPick(account)),
            const SizedBox(height: 8),
          ],
        ],
      ),
    );
  }
}

class _DemoAccountTile extends StatelessWidget {
  const _DemoAccountTile({required this.account, required this.onTap});

  final DemoAccount account;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Material(
      color: theme.cardColor,
      borderRadius: BorderRadius.circular(SkyTimeRadii.medium),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(SkyTimeRadii.medium),
        hoverColor: SkyTimeColors.teal.withValues(alpha: 0.08),
        child: Padding(
          padding: const EdgeInsets.fromLTRB(14, 12, 10, 12),
          child: Row(
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      account.title,
                      style: const TextStyle(fontSize: 13.5, fontWeight: FontWeight.w800),
                    ),
                    const SizedBox(height: 2),
                    Text(
                      '${account.email} · ${account.password}',
                      style: TextStyle(
                        fontSize: 12,
                        // Моноширинный — учётные данные копируют глазами,
                        // и одинаковая ширина знаков тут заметно помогает.
                        fontFamily: 'monospace',
                        color: theme.colorScheme.onSurface.withValues(alpha: 0.72),
                      ),
                    ),
                    const SizedBox(height: 3),
                    Text(account.description, style: theme.textTheme.bodySmall),
                  ],
                ),
              ),
              const SizedBox(width: 8),
              Tooltip(
                message: 'Подставить в форму',
                child: Icon(
                  Icons.login,
                  size: 18,
                  color: theme.colorScheme.onSurface.withValues(alpha: 0.5),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
