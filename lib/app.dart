import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import 'data/vegetation_data_service.dart';
import 'models/region.dart';
import 'screens/map_screen.dart';
import 'screens/region_detail_screen.dart';

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
          path: '/region/:id',
          builder: (context, state) {
            final region = state.extra as Region?;
            final id = state.pathParameters['id']!;
            if (region != null) {
              return RegionDetailScreen(service: service, region: region);
            }
            // Deep link without the Region object (e.g. page refresh on
            // web): fetch the region list and resolve it by id.
            return FutureBuilder<List<Region>>(
              future: service.getRegions(),
              builder: (context, snapshot) {
                if (!snapshot.hasData) {
                  return const Scaffold(
                    body: Center(child: CircularProgressIndicator()),
                  );
                }
                final found = snapshot.data!.where((r) => r.id == id);
                if (found.isEmpty) {
                  return const Scaffold(
                    body: Center(child: Text('Регион не найден')),
                  );
                }
                return RegionDetailScreen(service: service, region: found.first);
              },
            );
          },
        ),
      ],
    );

    return MaterialApp.router(
      title: 'Kosmohack NDVI',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorSchemeSeed: const Color(0xFF2E7D32),
        useMaterial3: true,
      ),
      routerConfig: router,
    );
  }
}
