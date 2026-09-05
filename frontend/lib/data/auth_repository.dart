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

  /// Восстанавливает сессию после перезагрузки страницы (если была
  /// сохранена) — без этого JWT/логин жили только в памяти, и обычный
  /// F5 разлогинивал пользователя, хотя на реальном бэкенде его полигоны
  /// никуда не делись. Вызывается один раз в `main()` до `runApp`.
  Future<void> init() async {}

  Future<RegistrationResult> register({
    required String email,
    required String password,
    String? fullName,
  });

  /// Подтверждает почту и сразу возвращает JWT — как и реальный бэкенд.
  /// [email] — не уходит на сервер (эндпоинт его не принимает), только для
  /// локального состояния (`this.email`, персистентность сессии): сам ответ
  /// `/auth/confirm-email` email не возвращает, а экран его уже знает
  /// из query-параметра `?email=` после регистрации/смены почты.
  Future<void> confirmEmail(String token, {String? email});

  Future<void> login({required String email, required String password});

  void logout();

  /// Новый пароль не применяется сразу — вступает в силу только после
  /// [confirmPasswordChange] с токеном, который тут возвращается (тот же
  /// принцип, что и у [changeEmail]: письмо со ссылкой дублирует токен,
  /// но не заменяет его — сессия/JWT при этом не трогается, в отличие от
  /// смены почты, так что дожидаться подтверждения прямо на этом экране
  /// не обязательно).
  Future<String> changePassword({required String oldPassword, required String newPassword});

  Future<void> confirmPasswordChange(String token);

  /// Смена email требует повторного подтверждения — сразу после вызова
  /// текущий токен становится недействительным (как и на бэкенде), новый
  /// приходит после [confirmEmail] с возвращённым токеном.
  Future<RegistrationResult> changeEmail({required String newEmail, required String password});
}
