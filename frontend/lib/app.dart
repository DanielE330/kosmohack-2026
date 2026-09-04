import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import 'data/vegetation_data_service.dart';
import 'models/ndvi_polygon.dart';
import 'screens/map_screen.dart';
import 'screens/polygon_detail_screen.dart';

class KosmohackApp extends StatelessWidget {
  const KosmohackApp({super.key, required this.service});

  final VegetationDataService service;

  @override
  Widget build(BuildContext context) {
    final router = GoRouter(
      routes: [
        GoRoute(
          path: '/',
          builder: (context, state) => MapScreen(service: service),
        ),
        GoRoute(
          path: '/polygon/:id',
          builder: (context, state) {
            final polygon = state.extra as NdviPolygon?;
            final id = state.pathParameters['id']!;
            if (polygon != null) {
              return PolygonDetailScreen(service: service, polygon: polygon);
            }
            // Диплинк без объекта полигона (например, обновление страницы
            // в вебе): загружаем список полигонов и находим нужный по id.
            return FutureBuilder<List<NdviPolygon>>(
              future: service.getPolygons(),
              builder: (context, snapshot) {
                if (!snapshot.hasData) {
                  return const Scaffold(
                    body: Center(child: CircularProgressIndicator()),
                  );
                }
                final found = snapshot.data!.where((p) => p.id == id);
                if (found.isEmpty) {
                  return const Scaffold(
                    body: Center(child: Text('Полигон не найден')),
                  );
                }
                return PolygonDetailScreen(service: service, polygon: found.first);
              },
            );
          },
        ),
      ],
    );

    return MaterialApp.router(
      title: 'SkyTime',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorSchemeSeed: const Color(0xFF2E7D32),
        useMaterial3: true,
      ),
      routerConfig: router,
    );
  }
}
