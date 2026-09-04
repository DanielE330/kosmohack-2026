import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../data/auth_repository.dart';

/// Подтверждение почты. Реальная отправка письма ещё не подключена
/// (см. tasks/backend.md) — токен приходит сразу в ответе на регистрацию
/// и передаётся сюда параметром URL, поле уже заполнено. Экран нужен и
/// для интерфейса «как будет выглядеть», и для того, чтобы сценарий
/// регистрация → подтверждение → вход можно было реально пройти уже
/// сейчас, без почтового сервиса.
class ConfirmEmailScreen extends StatefulWidget {
  const ConfirmEmailScreen({
    super.key,
    required this.auth,
    this.prefillToken,
    this.prefillEmail,
  });

  final AuthRepository auth;
  final String? prefillToken;
  final String? prefillEmail;

  @override
  State<ConfirmEmailScreen> createState() => _ConfirmEmailScreenState();
}

class _ConfirmEmailScreenState extends State<ConfirmEmailScreen> {
  late final TextEditingController _tokenController;
  bool _loading = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _tokenController = TextEditingController(text: widget.prefillToken ?? '');
  }

  @override
  void dispose() {
    _tokenController.dispose();
    super.dispose();
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
      await widget.auth.confirmEmail(token);
      if (!mounted) return;
      context.go('/');
    } catch (e) {
      if (!mounted) return;
      setState(() => _error = e.toString().replaceFirst('Exception: ', ''));
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          onPressed: () => context.go('/'),
        ),
        title: const Text('Подтверждение почты'),
      ),
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 460),
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                if (widget.prefillEmail != null) ...[
                  Text(
                    'Письмо для ${widget.prefillEmail}',
                    style: Theme.of(context).textTheme.titleMedium,
                    textAlign: TextAlign.center,
                  ),
                  const SizedBox(height: 8),
                ],
                Card(
                  color: Theme.of(context).colorScheme.surfaceContainerHighest,
                  child: const Padding(
                    padding: EdgeInsets.all(16),
                    child: Text(
                      'Реальная отправка писем пока не подключена, поэтому токен '
                      'подтверждения уже подставлен в поле ниже — просто нажмите '
                      '«Подтвердить». Когда подключим почту, это поле уберём и '
                      'токен будет приходить только в письме.',
                      style: TextStyle(fontSize: 13),
                    ),
                  ),
                ),
                const SizedBox(height: 20),
                TextField(
                  controller: _tokenController,
                  decoration: const InputDecoration(labelText: 'Токен подтверждения'),
                ),
                if (_error != null) ...[
                  const SizedBox(height: 12),
                  Text(_error!, style: TextStyle(color: Theme.of(context).colorScheme.error)),
                ],
                const SizedBox(height: 20),
                FilledButton(
                  onPressed: _loading ? null : _confirm,
                  child: _loading
                      ? const SizedBox(
                          width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2))
                      : const Text('Подтвердить'),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
