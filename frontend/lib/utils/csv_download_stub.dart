/// Реализация для не-веб платформ (VM-тесты, Android/iOS сборки) — тела
/// файлов `csv_download_web.dart`/`csv_download_stub.dart` выбираются
/// условным экспортом в `csv_download.dart` в зависимости от платформы,
/// поэтому `dart:html` никогда не попадает в VM-тесты (`flutter test`
/// падал бы на попытке загрузить `dart:html` вне браузера).
bool downloadCsv(String filename, String csvContent) => false;
