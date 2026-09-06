// ignore_for_file: avoid_web_libraries_in_flutter
import 'dart:convert';
import 'dart:html' as html;
import 'dart:typed_data';

/// Настоящее скачивание в браузере: Blob + временная ссылка `<a download>`,
/// сразу «кликнутая» кодом. Стандартный способ отдать файл из Flutter Web
/// без бэкенда — сам файл никогда не покидает вкладку пользователя.
bool downloadCsv(String filename, String csvContent) {
  // BOM в начале — иначе Excel на Windows определяет кодировку неверно и
  // ломает кириллицу вместо UTF-8. utf8.encode (не .codeUnits — это UTF-16
  // code units, не байты UTF-8) — иначе кириллица бьётся при скачивании.
  final bytes = [0xEF, 0xBB, 0xBF, ...utf8.encode(csvContent)];
  final blob = html.Blob([bytes], 'text/csv;charset=utf-8');
  final url = html.Url.createObjectUrlFromBlob(blob);
  html.AnchorElement(href: url)
    ..setAttribute('download', filename)
    ..click();
  html.Url.revokeObjectUrl(url);
  return true;
}

/// Готовый файл с бэкенда (`.xlsx`/`.zip`) — тот же приём с Blob и
/// «кликнутой» ссылкой, но байты не трогаем: Excel-книга и zip — бинарные,
/// любое перекодирование их ломает.
bool downloadBytes(String filename, Uint8List bytes, String mimeType) {
  final blob = html.Blob([bytes], mimeType);
  final url = html.Url.createObjectUrlFromBlob(blob);
  html.AnchorElement(href: url)
    ..setAttribute('download', filename)
    ..click();
  html.Url.revokeObjectUrl(url);
  return true;
}
