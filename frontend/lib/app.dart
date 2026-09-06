import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import 'data/active_map_controller.dart';
import 'data/api_exception.dart';
import 'data/auth_repository.dart';
import 'data/vegetation_data_service.dart';
import 'models/ndvi_polygon.dart';
import 'route_observer.dart';
import 'screens/account_screen.dart';
import 'screens/analytics_screen.dart';
import 'screens/confirm_email_screen.dart';
import 'screens/home_screen.dart';
import 'screens/login_screen.dart';
import 'screens/map_screen.dart';
import 'screens/notifications_screen.dart';
import 'screens/polygon_detail_screen.dart';
import 'screens/register_screen.dart';
import 'screens/reports_screen.dart';
import 'screens/settings_screen.dart';
import 'theme.dart';
import 'theme_controller.dart';

class KosmohackApp extends StatelessWidget {
  const KosmohackApp({
    super.key,
    required this.service,
    required this.auth,
    required this.themeController,
    required this.activeMapController,
  });

  final VegetationDataService service;
  final AuthRepository auth;
  final ThemeController themeController;
  final ActiveMapController activeMapController;

  @override
  Widget build(BuildContext context) {
    final router = GoRouter(
      observers: [routeObserver],
      routes: [
        GoRoute(
          path: '/',
          // Корень — главный экран: краткое приветствие, маленькое
          // интерактивное окошко-превью карты (те же демо-данные) и
          // описание того, что есть что. Полноразмерная карта живёт на
          // /map — так демо всё равно видно сразу, без лишних кликов, но
          // есть место и для пояснительного текста.
          builder: (context, state) => HomeScreen(service: service, auth: auth),
        ),
        GoRoute(
          path: '/map',
          builder: (context, state) => MapScreen(
            service: service,
            auth: auth,
            activeMapController: activeMapController,
            startDrawing: state.uri.queryParameters['draw'] == '1',
          ),
        ),
        GoRoute(
          path: '/polygon/:id',
          builder: (context, state) => _PolygonRoute(
            service: service,
            id: state.pathParameters['id']!,
            // Токен из ссылки «поделиться» — по нему участок с чужой карты
            // открывается и без входа (см. PolygonDetailScreen._share).
            shareToken: state.uri.queryParameters['share'],
            auth: auth,
          ),
        ),
        GoRoute(
          path: '/account',
          builder: (context, state) =>
              AccountScreen(service: service, auth: auth, activeMapController: activeMapController),
        ),
        GoRoute(
          path: '/analytics',
          builder: (context, state) =>
              AnalyticsScreen(service: service, auth: auth, activeMapController: activeMapController),
        ),
        GoRoute(
          path: '/notifications',
          builder: (context, state) =>
              NotificationsScreen(service: service, auth: auth, activeMapController: activeMapController),
        ),
        GoRoute(
          path: '/reports',
          builder: (context, state) =>
              ReportsScreen(service: service, auth: auth, activeMapController: activeMapController),
        ),
        GoRoute(
          path: '/settings',
          builder: (context, state) => SettingsScreen(
            auth: auth,
            themeController: themeController,
            activeMapController: activeMapController,
          ),
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

    return ListenableBuilder(
      listenable: themeController,
      builder: (context, _) => MaterialApp.router(
        title: 'SkyTime',
        debugShowCheckedModeBanner: false,
        theme: buildSkyTimeTheme(),
        darkTheme: buildSkyTimeDarkTheme(),
        themeMode: themeController.mode,
        routerConfig: router,
      ),
    );
  }
}

/// Разрешает полигон только по `id` (без `extra`) — так маршрут остаётся
/// корректным диплинком и не зависит от того, каким способом на него
/// перешли (см. комментарий у [routeObserver]).
class _PolygonRoute extends StatefulWidget {
  const _PolygonRoute({
    required this.service,
    required this.id,
    required this.auth,
    this.shareToken,
  });

  final VegetationDataService service;
  final String id;
  final String? shareToken;
  final AuthRepository auth;

  @override
  State<_PolygonRoute> createState() => _PolygonRouteState();
}

class _PolygonRouteState extends State<_PolygonRoute> {
  // Запрос заводится один раз, а не в build(): иначе любая перерисовка
  // (в т.ч. смена темы) заново дёргала бы бэкенд и мигала спиннером.
  late Future<NdviPolygon> _future = _load();

  Future<NdviPolygon> _load() =>
      widget.service.getPolygon(widget.id, shareToken: widget.shareToken);

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<NdviPolygon>(
      future: _future,
      builder: (context, snapshot) {
        if (snapshot.connectionState != ConnectionState.done) {
          return const Scaffold(body: Center(child: CircularProgressIndicator()));
        }
        final error = snapshot.error;
        if (error != null) return _errorScaffold(context, error);
        return PolygonDetailScreen(
          service: widget.service,
          polygon: snapshot.data!,
          auth: widget.auth,
        );
      },
    );
  }

  /// Ссылку на участок чаще всего открывают в чужом браузере, где никто не
  /// вошёл, поэтому «нет доступа» и «нет такого участка» надо разделять:
  /// 401 значит, что доступ, скорее всего, есть — но у аккаунта, а не у
  /// анонимной вкладки, и человеку надо предложить войти, а не тупик
  /// «Полигон не найден».
  Widget _errorScaffold(BuildContext context, Object error) {
    final api = error is ApiException ? error : null;
    final needsLogin = api?.isUnauthorized ?? false;
    final message = needsLogin
        ? 'Этот участок лежит на закрытой карте — войдите под аккаунтом, '
            'которому владелец дал доступ, или попросите у него ссылку заново.'
        : (api?.isNotFound ?? false)
            ? 'Полигон не найден'
            : 'Не удалось открыть участок: ${api?.message ?? error}';

    return Scaffold(
      appBar: AppBar(
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          onPressed: () => context.go('/map'),
        ),
        title: const Text('Участок'),
      ),
      body: Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(message, textAlign: TextAlign.center),
              const SizedBox(height: 16),
              if (needsLogin)
                FilledButton(
                  onPressed: () => context.go('/login'),
                  child: const Text('Войти'),
                )
              else
                OutlinedButton(
                  onPressed: () => setState(() => _future = _load()),
                  child: const Text('Повторить'),
                ),
            ],
          ),
        ),
      ),
    );
  }
}
