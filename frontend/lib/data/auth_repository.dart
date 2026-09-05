import 'package:flutter/foundation.dart';

/// Результат регистрации. Пока не подключена реальная отправка почты
/// (см. tasks/backend.md) — токен подтверждения приходит сразу в ответе
/// на регистрацию, а не письмом. [ConfirmEmailScreen] использует его,
/// чтобы можно было пройти весь сценарий без настоящего email-сервиса.
class RegistrationResult {
  const RegistrationResult({required this.email, required this.confirmationToken});
  final String email;
  final String confirmationToken;
}

/// Контракт авторизации: регистрация → подтверждение почты → вход.
/// [MockAuthRepository] эмулирует это полностью в памяти (для демо-режима
/// без бэкенда), [HttpAuthRepository] говорит с реальным `/auth/*`.
abstract class AuthRepository extends ChangeNotifier {
  String? get token;
  String? get email;
  bool get isLoggedIn => token != null;

  Future<RegistrationResult> register({
    required String email,
    required String password,
    String? fullName,
  });

  /// Подтверждает почту и сразу возвращает JWT — как и реальный бэкенд.
  Future<void> confirmEmail(String token);

  Future<void> login({required String email, required String password});

  void logout();

  Future<void> changePassword({required String oldPassword, required String newPassword});

  /// Смена email требует повторного подтверждения — сразу после вызова
  /// текущий токен становится недействительным (как и на бэкенде), новый
  /// приходит после [confirmEmail] с возвращённым токеном.
  Future<RegistrationResult> changeEmail({required String newEmail, required String password});
}
