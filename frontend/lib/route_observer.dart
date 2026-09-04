import 'package:flutter/material.dart';

/// Стандартный Flutter-механизм «узнать, что экран снова стал видимым»
/// (после `pop`, из какого бы источника он ни пришёл — кнопка в
/// приложении или браузерная «назад»). Раньше `MapScreen` перезапрашивал
/// данные только через `await context.push(...)`, а этот `Future` не
/// завершается корректно при навигации браузерной кнопкой «назад» —
/// go_router в этом случае перестраивает стек по URL напрямую, из-за
/// расхождения состояния падал с `Bad state: No element`. RouteObserver
/// работает по жизненному циклу самого Navigator и не зависит от того,
/// как именно пользователь ушёл и вернулся.
final RouteObserver<PageRoute<void>> routeObserver = RouteObserver<PageRoute<void>>();
