import 'dart:convert';

import 'package:http/http.dart' as http;

import 'auth_repository.dart';

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
  Future<void> confirmEmail(String token) async {
    final res = await _client.post(
      _uri('/auth/confirm-email'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'token': token}),
    );
    if (res.statusCode != 200) throw Exception(_extractError(res));
    final data = jsonDecode(res.body) as Map<String, dynamic>;
    _token = data['access_token'] as String;
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
    notifyListeners();
  }

  @override
  void logout() {
    _token = null;
    _email = null;
    notifyListeners();
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
