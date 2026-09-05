import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../data/active_map_controller.dart';
import '../data/auth_repository.dart';
import '../data/status_transition_tracker.dart';
import '../data/vegetation_data_service.dart';
import '../utils/ndvi_style.dart';
import '../widgets/dashboard_shell.dart';

/// Уведомление = переход статуса участка через границу «штатно / не
/// штатно» с прошлого визита на этот экран (см.
/// `data/status_transition_tracker.dart`) — не любое изменение Z-score и
/// не полный список исторических аномалий, как было раньше: пользователю
/// важно узнать именно про смену состояния, а не пересматривать одно и то
/// же при каждом заходе.
class NotificationsScreen extends StatefulWidget {
  const NotificationsScreen({super.key, required this.service, required this.auth, required this.activeMapController});

  final VegetationDataService service;
  final AuthRepository auth;
  final ActiveMapController activeMapController;

  @override
  State<NotificationsScreen> createState() => _NotificationsScreenState();
}

class _NotificationsScreenState extends State<NotificationsScreen> {
  List<StatusTransition> _transitions = [];
  final Map<String, String> _explanations = {};
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    widget.auth.addListener(_load);
    widget.activeMapController.addListener(_load);
    _load();
  }

  @override
  void dispose() {
    widget.auth.removeListener(_load);
    widget.activeMapController.removeListener(_load);
    super.dispose();
  }

  Future<void> _load() async {
    // Без входа своих полигонов не бывает — не ходим в сеть вообще, иначе
    // лента молча крутится бесконечно для незалогиненного посетителя.
    if (!widget.auth.isLoggedIn) {
      setState(() {
        _transitions = [];
        _loading = false;
        _error = null;
      });
      return;
    }
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final tracker = StatusTransitionTracker.instance;
      await tracker.refresh(widget.activeMapController);
      final transitions = tracker.lastTransitions;

      // Объяснение — для контекста у тех, кто стал "не штатно": последняя
      // известная аномалия по этому участку, если она уже посчитана.
      if (transitions.any((t) => !t.isImprovement)) {
        final all = await widget.service.getAnomalies();
        for (final t in transitions) {
          if (t.isImprovement) continue;
          final own = all.where((a) => a.polygonId == t.polygon.id).toList()
            ..sort((a, b) => b.startDate.compareTo(a.startDate));
          if (own.isNotEmpty) _explanations[t.polygon.id] = own.first.explanation;
        }
      }

      setState(() {
        _transitions = transitions;
        _loading = false;
      });
      // Пользователь увидел список — переходы больше не "непросмотренные"
      // (сбрасывает и бейдж на "Уведомления" в сайдбаре).
      await tracker.markSeen();
    } catch (e) {
      setState(() {
        _error = 'Не удалось загрузить уведомления: $e';
        _loading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return DashboardShell(
      active: DashboardSection.notifications,
      activeMapController: widget.activeMapController,
      child: Scaffold(
        appBar: AppBar(
          leading: IconButton(
            icon: const Icon(Icons.arrow_back),
            onPressed: () => context.go('/map'),
          ),
          title: const Text('Уведомления'),
        ),
        body: RefreshIndicator(
          onRefresh: _load,
          child: _loading
              ? const Center(child: CircularProgressIndicator())
              : ListView(
                  padding: const EdgeInsets.all(16),
                  children: [
                    if (_error != null)
                      Padding(padding: const EdgeInsets.symmetric(vertical: 12), child: Text(_error!))
                    else if (_transitions.isEmpty)
                      const Padding(
                        padding: EdgeInsets.symmetric(vertical: 12),
                        child: Text(
                          'Новых изменений статуса нет — либо всё стабильно, либо вы уже '
                          'видели последние переходы.',
                        ),
                      )
                    else
                      for (final t in _transitions)
                        _TransitionTile(
                          transition: t,
                          explanation: _explanations[t.polygon.id],
                          onTap: () => context.go('/polygon/${t.polygon.id}'),
                        ),
                  ],
                ),
        ),
      ),
    );
  }
}

class _TransitionTile extends StatelessWidget {
  const _TransitionTile({required this.transition, required this.explanation, required this.onTap});

  final StatusTransition transition;
  final String? explanation;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final color = statusColor(transition.to);
    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Icon(
                transition.isImprovement ? Icons.trending_up : Icons.trending_down,
                color: color,
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(transition.polygon.label,
                        style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 13.5)),
                    const SizedBox(height: 2),
                    Text(
                      '${statusLabel(transition.from)} → ${statusLabel(transition.to)}',
                      style: TextStyle(fontSize: 12, color: Theme.of(context).hintColor),
                    ),
                    if (explanation != null && explanation!.isNotEmpty) ...[
                      const SizedBox(height: 6),
                      Text(explanation!, style: const TextStyle(fontSize: 12.5)),
                    ],
                  ],
                ),
              ),
              const SizedBox(width: 8),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
                decoration: BoxDecoration(color: color.withValues(alpha: 0.15), borderRadius: BorderRadius.circular(999)),
                child: Text(
                  transition.isImprovement ? 'Улучшилось' : 'Ухудшилось',
                  style: TextStyle(fontSize: 10.5, fontWeight: FontWeight.w700, color: color),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
