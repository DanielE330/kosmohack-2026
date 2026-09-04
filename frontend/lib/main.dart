import 'package:flutter/material.dart';
import 'package:intl/date_symbol_data_local.dart';

import 'app.dart';
import 'data/http_vegetation_data_service.dart';
import 'data/mock_vegetation_data_service.dart';
import 'data/vegetation_data_service.dart';

/// Pass --dart-define=API_BASE_URL=http://host:port to point the app at the
/// real backend once it's up. Without it, the app runs fully on mock data.
const _apiBaseUrl = String.fromEnvironment('API_BASE_URL');

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await initializeDateFormatting('ru');

  final VegetationDataService service = _apiBaseUrl.isEmpty
      ? MockVegetationDataService()
      : HttpVegetationDataService(baseUrl: _apiBaseUrl);

  runApp(KosmohackApp(service: service));
}
