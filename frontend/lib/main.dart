import 'package:flutter/material.dart';
import 'package:intl/date_symbol_data_local.dart';

import 'app.dart';
import 'data/auth_repository.dart';
import 'data/http_auth_repository.dart';
import 'data/http_vegetation_data_service.dart';
import 'data/mock_auth_repository.dart';
import 'data/mock_vegetation_data_service.dart';
import 'data/vegetation_data_service.dart';

/// Передайте --dart-define=API_BASE_URL=http://host:port, чтобы направить
/// приложение на реальный бэкенд. Без этого флага работает полностью на
/// моковых данных.
const _apiBaseUrl = String.fromEnvironment('API_BASE_URL');

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await initializeDateFormatting('ru');

  late final VegetationDataService service;
  late final AuthRepository auth;
  if (_apiBaseUrl.isEmpty) {
    final mockAuth = MockAuthRepository();
    service = MockVegetationDataService();
    auth = mockAuth;
  } else {
    final httpAuth = HttpAuthRepository(baseUrl: _apiBaseUrl);
    service = HttpVegetationDataService(baseUrl: _apiBaseUrl, tokenProvider: () => httpAuth.token);
    auth = httpAuth;
  }

  runApp(KosmohackApp(service: service, auth: auth));
}
