import 'dart:async';

import 'package:shared_preferences/shared_preferences.dart';

import 'auth_repository.dart';

const _kTokenKey = 'auth_token';
const _kEmailKey = 'auth_email';

class _MockUser {
  _MockUser({required this.email, required this.password, this.fullName});
  String email;
  String password;
  final String? fullName;
  bool confirmed = false;
  String? confirmationToken;
}

/// Эмулирует весь цикл регистрация → подтверждение → вход в памяти, без
/// бэкенда — чтобы экраны авторизации можно было показать и на демо-моке.
class MockAuthRepository extends AuthRepository {
  final Map<String, _MockUser> _users = {};
  int _tokenCounter = 0;
  String? _token;
  String? _email;

  /// Готовый демо-аккаунт — чтобы можно было сразу войти на моке, не
  /// проходя регистрацию (её всё равно можно пройти отдельно, с любым
  /// другим email).
  static const demoEmail = 'demo@skytime.dev';
  static const demoPassword = 'demo1234';

  MockAuthRepository() {
    _users[demoEmail] = _MockUser(email: demoEmail, password: demoPassword)..confirmed = true;
  }

  @override
  String? get token => _token;

  @override
  String? get email => _email;

  /// В моке весь `_users` живёт только в памяти и создаётся заново при
  /// каждой перезагрузке страницы — восстановить сессию по-настоящему
  /// можно только для встроенного демо-аккаунта (он всегда есть заново);
  /// для остальных, зарегистрированных за сессию, честнее разлогинить и
  /// дать войти заново, чем притвориться вошедшим в несуществующего
  /// пользователя.
  @override
  Future<void> init() async {
    final prefs = await SharedPreferences.getInstance();
    final savedToken = prefs.getString(_kTokenKey);
    final savedEmail = prefs.getString(_kEmailKey);
    if (savedToken != null && savedEmail != null && _users.containsKey(savedEmail)) {
      _token = savedToken;
      _email = savedEmail;
    } else {
      await prefs.remove(_kTokenKey);
      await prefs.remove(_kEmailKey);
    }
  }

  Future<void> _persist() async {
    final prefs = await SharedPreferences.getInstance();
    if (_token == null) {
      await prefs.remove(_kTokenKey);
      await prefs.remove(_kEmailKey);
    } else {
      await prefs.setString(_kTokenKey, _token!);
      await prefs.setString(_kEmailKey, _email!);
    }
  }

  @override
  Future<RegistrationResult> register({
    required String email,
    required String password,
    String? fullName,
  }) async {
    if (_users.containsKey(email)) {
      throw Exception('Пользователь с таким email уже зарегистрирован');
    }
    _tokenCounter++;
    final confirmationToken = 'mock-confirm-$_tokenCounter';
    _users[email] = _MockUser(email: email, password: password, fullName: fullName)
      ..confirmationToken = confirmationToken;
    return RegistrationResult(email: email, confirmationToken: confirmationToken);
  }

  @override
  Future<void> confirmEmail(String token, {String? email}) async {
    _MockUser? user;
    for (final u in _users.values) {
      if (u.confirmationToken == token) {
        user = u;
        break;
      }
    }
    if (user == null) {
      throw Exception('Неверный или уже использованный токен');
    }
    user.confirmed = true;
    user.confirmationToken = null;
    _tokenCounter++;
    _token = 'mock-token-$_tokenCounter';
    _email = user.email;
    await _persist();
    notifyListeners();
  }

  @override
  Future<void> login({required String email, required String password}) async {
    final user = _users[email];
    if (user == null || user.password != password) {
      throw Exception('Неверный email или пароль');
    }
    if (!user.confirmed) {
      throw Exception('Почта не подтверждена');
    }
    _tokenCounter++;
    _token = 'mock-token-$_tokenCounter';
    _email = user.email;
    await _persist();
    notifyListeners();
  }

  @override
  void logout() {
    _token = null;
    _email = null;
    unawaited(_persist());
    notifyListeners();
  }

  @override
  Future<void> changePassword({required String oldPassword, required String newPassword}) async {
    final user = _users[_email];
    if (user == null || user.password != oldPassword) {
      throw Exception('Неверный текущий пароль');
    }
    user.password = newPassword;
  }

  @override
  Future<RegistrationResult> changeEmail({required String newEmail, required String password}) async {
    final user = _users[_email];
    if (user == null || user.password != password) {
      throw Exception('Неверный пароль');
    }
    if (_users.containsKey(newEmail)) {
      throw Exception('Этот email уже занят');
    }
    _users.remove(user.email);
    user.email = newEmail;
    user.confirmed = false;
    _tokenCounter++;
    final confirmationToken = 'mock-confirm-$_tokenCounter';
    user.confirmationToken = confirmationToken;
    _users[newEmail] = user;
    _token = null;
    _email = null;
    await _persist();
    notifyListeners();
    return RegistrationResult(email: newEmail, confirmationToken: confirmationToken);
  }
}
