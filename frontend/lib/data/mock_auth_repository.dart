import 'auth_repository.dart';

class _MockUser {
  _MockUser({required this.email, required this.password, this.fullName});
  final String email;
  final String password;
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

  @override
  String? get token => _token;

  @override
  String? get email => _email;

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
  Future<void> confirmEmail(String token) async {
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
    notifyListeners();
  }

  @override
  void logout() {
    _token = null;
    _email = null;
    notifyListeners();
  }
}
