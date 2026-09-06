import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../data/auth_repository.dart';
import '../theme.dart';
import '../widgets/auth_scaffold.dart';

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
      await widget.auth.confirmEmail(token, email: widget.prefillEmail);
      if (!mounted) return;
      context.go('/map');
    } catch (e) {
      if (!mounted) return;
      setState(() => _error = e.toString().replaceFirst('Exception: ', ''));
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    // Та же рамка, что на входе и регистрации — это третий шаг одного и
    // того же сценария, и выглядеть он должен так же.
    return AuthScaffold(
      title: 'Подтверждение почты',
      subtitle: widget.prefillEmail == null
          ? 'Введите токен из письма'
          : 'Письмо для ${widget.prefillEmail}',
      form: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Container(
            padding: const EdgeInsets.all(14),
            decoration: BoxDecoration(
              color: SkyTimeColors.teal.withValues(alpha: 0.10),
              borderRadius: BorderRadius.circular(SkyTimeRadii.medium),
              border: Border.all(color: SkyTimeColors.teal.withValues(alpha: 0.3)),
            ),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Icon(Icons.mark_email_read_outlined, size: 18, color: SkyTimeColors.teal),
                const SizedBox(width: 10),
                Expanded(
                  child: Text(
                    'Токен подтверждения также должен прийти письмом — но на '
                    'случай, если почта задержится или не дойдёт, он уже '
                    'подставлен в поле ниже: просто нажмите «Подтвердить».',
                    style: theme.textTheme.bodySmall,
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 20),
          TextField(
            controller: _tokenController,
            decoration: const InputDecoration(
              labelText: 'Токен подтверждения',
              prefixIcon: Icon(Icons.key_outlined, size: 20),
            ),
          ),
          if (_error != null) ...[
            const SizedBox(height: 16),
            AuthErrorBanner(message: _error!),
          ],
          const SizedBox(height: 22),
          FilledButton(
            onPressed: _loading ? null : _confirm,
            child: _loading
                ? const SizedBox(
                    width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2))
                : const Text('Подтвердить'),
          ),
        ],
      ),
    );
  }
}
