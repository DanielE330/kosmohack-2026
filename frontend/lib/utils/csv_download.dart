/// Скачивание файлов из браузера:
///   `downloadCsv(filename, csvContent) -> bool` — CSV, собранный на клиенте;
///   `downloadBytes(filename, bytes, mimeType) -> bool` — готовый файл с
///   бэкенда (Excel-отчёт `.xlsx` / архив `.zip`).
/// Возвращают `true`, если скачивание реально началось.
///
/// На вебе — настоящее скачивание через `dart:html`; на остальных
/// платформах (VM-тесты, будущие Android/iOS сборки) — заглушка, всегда
/// `false`, так UI может показать «не поддерживается на этой платформе».
library;

export 'csv_download_stub.dart' if (dart.library.html) 'csv_download_web.dart';
