import 'package:flutter/material.dart';

/// Переключатель светлой/тёмной темы — только в памяти, без сохранения
/// между перезагрузками (упрощение: в проекте пока нет зависимости для
/// персистентного хранилища на вебе/мобиле, а для хакатона не критично).
class ThemeController extends ChangeNotifier {
  ThemeMode _mode = ThemeMode.light;

  ThemeMode get mode => _mode;
  bool get isDark => _mode == ThemeMode.dark;

  void toggle() {
    _mode = _mode == ThemeMode.dark ? ThemeMode.light : ThemeMode.dark;
    notifyListeners();
  }
}
