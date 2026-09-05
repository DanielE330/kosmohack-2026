/// `downloadCsv(filename, csvContent) -> bool` (true — реально скачалось).
/// На вебе — настоящее скачивание через `dart:html`; на остальных
/// платформах (VM-тесты, будущие Android/iOS сборки) — заглушка, всегда
/// `false`, так UI может показать «не поддерживается на этой платформе».
library;

export 'csv_download_stub.dart' if (dart.library.html) 'csv_download_web.dart';
