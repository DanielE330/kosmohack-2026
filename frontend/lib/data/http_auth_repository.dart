import 'dart:async';
import 'dart:convert';

import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

import 'auth_repository.dart';

const _kTokenKey = 'auth_token';
const _kEmailKey = 'auth_email';

/// Говорит с реальным `/auth/register`, `/auth/confirm-email`,
/// `/auth/login` (см. backend/app/api/routes/auth.py).
class HttpAuthRepository extends AuthRepository {
  HttpAuthRepository({required this.baseUrl, http.Client? client})
      : _client = client ?? http.Client();

  final String baseUrl;
  final http.Client _client;
  String? _token;
  String? _email;

  @override
  String? get token => _token;

  @override
  String? get email => _email;

  /// JWT не истекает быстро (`ACCESS_TOKEN_EXPIRE_MINUTES` — сутки), и сам
  /// полигон/данные пользователя реально живут на сервере — без сохранения
  /// токена обычная перезагрузка страницы выглядела как «пропали все
  /// полигоны», хотя на деле просто терялась сессия в памяти.
  @override
  Future<void> init() async {
    final prefs = await SharedPreferences.getInstance();
    _token = prefs.getString(_kTokenKey);
    _email = prefs.getString(_kEmailKey);
  }

  Future<void> _persist() async {
    final prefs = await SharedPreferences.getInstance();
    if (_token == null) {
      await prefs.remove(_kTokenKey);
      await prefs.remove(_kEmailKey);
    } else {
      await prefs.setString(_kTokenKey, _token!);
      if (_email != null) await prefs.setString(_kEmailKey, _email!);
    }
  }

  Uri _uri(String path) => Uri.parse('$baseUrl$path');

  @override
  Future<RegistrationResult> register({
    required String email,
    required String password,
    String? fullName,
  }) async {
    final res = await _client.post(
      _uri('/auth/register'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'email': email, 'password': password, 'full_name': fullName}),
    );
    if (res.statusCode != 201) throw Exception(_extractError(res));
    final data = jsonDecode(res.body) as Map<String, dynamic>;
    return RegistrationResult(
      email: data['email'] as String,
      confirmationToken: data['email_confirmation_token'] as String,
    );
  }

  @override
  Future<void> confirmEmail(String token, {String? email}) async {
    final res = await _client.post(
      _uri('/auth/confirm-email'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'token': token}),
    );
    if (res.statusCode != 200) throw Exception(_extractError(res));
    final data = jsonDecode(res.body) as Map<String, dynamic>;
    _token = data['access_token'] as String;
    _email = email ?? _email;
    await _persist();
    notifyListeners();
  }

  @override
  Future<void> login({required String email, required String password}) async {
    final res = await _client.post(
      _uri('/auth/login'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'email': email, 'password': password}),
    );
    if (res.statusCode != 200) throw Exception(_extractError(res));
    final data = jsonDecode(res.body) as Map<String, dynamic>;
    _token = data['access_token'] as String;
    _email = email;
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
    final res = await _client.post(
      _uri('/auth/change-password'),
      headers: {'Content-Type': 'application/json', 'Authorization': 'Bearer $_token'},
      body: jsonEncode({'old_password': oldPassword, 'new_password': newPassword}),
    );
    if (res.statusCode != 204) throw Exception(_extractError(res));
  }

  @override
  Future<RegistrationResult> changeEmail({required String newEmail, required String password}) async {
    final res = await _client.post(
      _uri('/auth/change-email'),
      headers: {'Content-Type': 'application/json', 'Authorization': 'Bearer $_token'},
      body: jsonEncode({'new_email': newEmail, 'password': password}),
    );
    if (res.statusCode != 200) throw Exception(_extractError(res));
    final data = jsonDecode(res.body) as Map<String, dynamic>;
    // Старый JWT привязан к старому email и сразу перестаёт быть валидным
    // на сервере — разлогиниваем, пока новый адрес не подтверждён.
    _token = null;
    _email = null;
    await _persist();
    notifyListeners();
    return RegistrationResult(
      email: data['email'] as String,
      confirmationToken: data['email_confirmation_token'] as String,
    );
  }

  String _extractError(http.Response res) {
    try {
      final data = jsonDecode(res.body);
      if (data is Map && data['detail'] != null) return data['detail'].toString();
    } catch (_) {
      // тело не JSON — покажем как есть
    }
    return res.body;
  }
}
