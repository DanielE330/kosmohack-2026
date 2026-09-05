import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../models/ndvi_point.dart';
import '../models/ndvi_polygon.dart';
import 'active_map_controller.dart';

const _kSeenStatusPrefix = 'status_seen_';

/// Один переход статуса участка через границу «штатно / не штатно» —
/// единственное, что в этом проекте считается «уведомлением» (не любое
/// изменение Z-score, и не переход suppression↔critical — оба этих
/// статуса уже "не штатно", смена одного на другой не пересекает границу).
class StatusTransition {
  const StatusTransition({required this.polygon, required this.from, required this.to});

  final NdviPolygon polygon;
  final NdviStatus from;
  final NdviStatus to;

  /// `true` — участок вернулся в норму, `false` — стало хуже.
  bool get isImprovement => to == NdviStatus.normal;
}

/// Отслеживает последний увиденный пользователем статус каждого своего
/// участка (persist через `shared_preferences`, переживает перезагрузку —
/// тот же паттерн, что `ActiveMapController`) и вычисляет, у каких участков
/// статус пересёк границу «штатно / не штатно» с прошлого раза. Синглтон,
/// а не что-то, что нужно явно прокидывать через конструкторы экранов —
/// сайдбар (`dashboard_shell.dart`) должен видеть счётчик независимо от
/// того, какой именно экран сейчас открыт.
class StatusTransitionTracker {
  StatusTransitionTracker._();

  static final StatusTransitionTracker instance = StatusTransitionTracker._();

  /// Сколько непросмотренных переходов найдено при последнем `refresh()` —
  /// сайдбар слушает это напрямую, без похода в сеть самостоятельно.
  final ValueNotifier<int> unseenCount = ValueNotifier(0);

  List<StatusTransition> _lastTransitions = const [];
  List<StatusTransition> get lastTransitions => _lastTransitions;

  Map<String, NdviStatus> _lastCurrentStatuses = const {};

  bool _refreshing = false;

  /// Перезагружает свои полигоны активной карты, считает текущий статус
  /// каждого (последняя точка временного ряда) и сравнивает с сохранённым.
  /// Безопасно вызывать многократно/параллельно (напр. из каждого нового
  /// `_Sidebar` при навигации) — повторные вызовы, пока первый ещё не
  /// завершился, просто ничего не делают.
  Future<void> refresh(ActiveMapController controller) async {
    if (_refreshing) return;
    if (!controller.auth.isLoggedIn) {
      _lastTransitions = const [];
      _lastCurrentStatuses = const {};
      unseenCount.value = 0;
      return;
    }
    _refreshing = true;
    try {
      final polygons = await controller.service.getPolygons(mapId: controller.active?.id);
      final mine = polygons.where((p) => p.isCustom).toList();
      final series = await Future.wait(mine.map((p) => controller.service.getTimeseries(p.id)));
      final prefs = await SharedPreferences.getInstance();

      final currentStatuses = <String, NdviStatus>{};
      final transitions = <StatusTransition>[];
      for (var i = 0; i < mine.length; i++) {
        if (series[i].isEmpty) continue;
        final current = series[i].last.status;
        currentStatuses[mine[i].id] = current;

        final storedName = prefs.getString('$_kSeenStatusPrefix${mine[i].id}');
        final stored = storedName == null ? null : _statusByName(storedName);
        if (stored != null &&
            stored != current &&
            (stored == NdviStatus.normal) != (current == NdviStatus.normal)) {
          transitions.add(StatusTransition(polygon: mine[i], from: stored, to: current));
        }
      }

      _lastCurrentStatuses = currentStatuses;
      _lastTransitions = transitions;
      unseenCount.value = transitions.length;
    } catch (_) {
      // Сеть подвела — не критично, просто не обновляем счётчик сейчас;
      // следующая навигация между экранами попробует снова.
    } finally {
      _refreshing = false;
    }
  }

  /// Помечает все статусы, посчитанные при последнем `refresh()`, как
  /// увиденные — вызывается экраном уведомлений после показа списка.
  Future<void> markSeen() async {
    if (_lastCurrentStatuses.isEmpty && unseenCount.value == 0) return;
    final prefs = await SharedPreferences.getInstance();
    for (final entry in _lastCurrentStatuses.entries) {
      await prefs.setString('$_kSeenStatusPrefix${entry.key}', entry.value.name);
    }
    _lastTransitions = const [];
    unseenCount.value = 0;
  }

  NdviStatus? _statusByName(String name) {
    for (final s in NdviStatus.values) {
      if (s.name == name) return s;
    }
    return null;
  }
}
