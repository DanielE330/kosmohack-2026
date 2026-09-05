import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../models/map_info.dart';
import 'auth_repository.dart';
import 'vegetation_data_service.dart';

const _kActiveMapIdKey = 'active_map_id';

/// Какая карта сейчас выбрана (выпадающее меню в сайдбаре, см.
/// `widgets/dashboard_shell.dart`) — определяет, чьи полигоны видно на
/// `/map` и куда попадает вновь нарисованный полигон. Выбор переживает
/// перезагрузку страницы (shared_preferences), как и сама сессия
/// (см. `AuthRepository.init`).
class ActiveMapController extends ChangeNotifier {
  ActiveMapController({required this.service, required this.auth}) {
    auth.addListener(_onAuthChanged);
  }

  final VegetationDataService service;
  final AuthRepository auth;

  List<MapInfo> _maps = [];
  MapInfo? _active;
  bool _loading = false;

  List<MapInfo> get maps => _maps;
  MapInfo? get active => _active;
  bool get loading => _loading;

  /// Пока идёт первая загрузка после логина — карт ещё не видно,
  /// но это не то же самое, что "у пользователя нет карт".
  bool get isLoggedIn => auth.isLoggedIn;

  void _onAuthChanged() {
    if (auth.isLoggedIn) {
      reload();
    } else {
      _maps = [];
      _active = null;
      notifyListeners();
    }
  }

  Future<void> reload() async {
    if (!auth.isLoggedIn) return;
    _loading = true;
    notifyListeners();
    try {
      final maps = await service.getMaps();
      final prefs = await SharedPreferences.getInstance();
      final savedId = prefs.getInt(_kActiveMapIdKey);
      MapInfo? restored;
      if (savedId != null) {
        for (final m in maps) {
          if (m.id == savedId) restored = m;
        }
      }
      _maps = maps;
      _active = restored ?? (maps.isNotEmpty ? maps.first : null);
      _loading = false;
      notifyListeners();
    } catch (_) {
      _loading = false;
      notifyListeners();
    }
  }

  Future<void> select(MapInfo map) async {
    _active = map;
    notifyListeners();
    final prefs = await SharedPreferences.getInstance();
    await prefs.setInt(_kActiveMapIdKey, map.id);
  }

  Future<MapInfo> create(String name) async {
    final map = await service.createMap(name);
    _maps = [..._maps, map];
    await select(map);
    return map;
  }
}
