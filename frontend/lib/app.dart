import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import 'data/auth_repository.dart';
import 'data/vegetation_data_service.dart';
import 'models/ndvi_polygon.dart';
import 'route_observer.dart';
import 'screens/account_screen.dart';
import 'screens/confirm_email_screen.dart';
import 'screens/landing_screen.dart';
import 'screens/login_screen.dart';
import 'screens/map_screen.dart';
import 'screens/polygon_detail_screen.dart';
import 'screens/register_screen.dart';
import 'theme.dart';

class KosmohackApp extends StatelessWidget {
  const KosmohackApp({
    super.key,
    required this.service,
    required this.auth,
  });

  final VegetationDataService service;
  final AuthRepository auth;

  @override
  Widget build(BuildContext context) {
    final router = GoRouter(
      observers: [routeObserver],
      routes: [
        GoRoute(
          path: '/',
          // Корень — лендинг: краткое приветствие, маленькое интерактивное
          // окошко-превью карты (те же демо-данные) и описание того, что
          // есть что. Полноразмерная карта живёт на /map — так демо всё
          // равно видно сразу, без лишних кликов, но есть место и для
          // пояснительного текста.
          builder: (context, state) => LandingScreen(service: service, auth: auth),
        ),
        GoRoute(
          path: '/map',
          builder: (context, state) => MapScreen(
            service: service,
            auth: auth,
            startDrawing: state.uri.queryParameters['draw'] == '1',
          ),
        ),
        GoRoute(
          path: '/polygon/:id',
          builder: (context, state) => _PolygonRoute(
            service: service,
            id: state.pathParameters['id']!,
            auth: auth,
          ),
        ),
        GoRoute(
          path: '/account',
          builder: (context, state) => AccountScreen(service: service, auth: auth),
        ),
        GoRoute(
          path: '/login',
          builder: (context, state) => LoginScreen(auth: auth),
        ),
        GoRoute(
          path: '/register',
          builder: (context, state) => RegisterScreen(auth: auth),
        ),
        GoRoute(
          path: '/confirm-email',
          builder: (context, state) => ConfirmEmailScreen(
            auth: auth,
            prefillToken: state.uri.queryParameters['token'],
            prefillEmail: state.uri.queryParameters['email'],
          ),
        ),
      ],
    );

    return MaterialApp.router(
      title: 'SkyTime',
      debugShowCheckedModeBanner: false,
      theme: buildSkyTimeTheme(),
      routerConfig: router,
    );
  }
}

/// Разрешает полигон только по `id` (без `extra`) — так маршрут остаётся
/// корректным диплинком и не зависит от того, каким способом на него
/// перешли (см. комментарий у [routeObserver]).
class _PolygonRoute extends StatelessWidget {
  const _PolygonRoute({required this.service, required this.id, required this.auth});

  final VegetationDataService service;
  final String id;
  final AuthRepository auth;

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<List<NdviPolygon>>(
      future: service.getPolygons(),
      builder: (context, snapshot) {
        if (!snapshot.hasData) {
          return const Scaffold(body: Center(child: CircularProgressIndicator()));
        }
        final found = snapshot.data!.where((p) => p.id == id);
        if (found.isEmpty) {
          return const Scaffold(body: Center(child: Text('Полигон не найден')));
        }
        return PolygonDetailScreen(service: service, polygon: found.first, auth: auth);
      },
    );
  }
}
