import 'package:flutter/material.dart';
import 'package:flutter_web_plugins/url_strategy.dart';
import 'package:intl/date_symbol_data_local.dart';

import 'app.dart';
import 'data/active_map_controller.dart';
import 'data/auth_repository.dart';
import 'data/http_auth_repository.dart';
import 'data/http_vegetation_data_service.dart';
import 'data/mock_auth_repository.dart';
import 'data/mock_vegetation_data_service.dart';
import 'data/vegetation_data_service.dart';
import 'theme_controller.dart';

/// Передайте --dart-define=API_BASE_URL=http://host:port, чтобы направить
/// приложение на реальный бэкенд. Без этого флага работает полностью на
/// моковых данных.
const _apiBaseUrl = String.fromEnvironment('API_BASE_URL');

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  usePathUrlStrategy();
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

  await auth.init();
  final activeMapController = ActiveMapController(service: service, auth: auth);
  if (auth.isLoggedIn) await activeMapController.reload();
  runApp(KosmohackApp(
    service: service,
    auth: auth,
    themeController: ThemeController(),
    activeMapController: activeMapController,
  ));
}
